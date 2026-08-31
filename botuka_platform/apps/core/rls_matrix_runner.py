import csv
import json
import os
import re
from collections import defaultdict
from contextlib import ExitStack
from contextvars import ContextVar
from pathlib import Path
from unittest import TextTestResult, TextTestRunner

from django.db import connections, transaction
from django.test.runner import DiscoverRunner

from .db_routing import current_executor, database_executor
from .db_middleware import request_database_alias

_CURRENT_TEST = ContextVar("rls_matrix_test", default="test_setup")
_ACTIVE_RUNTIME_FLOW = ContextVar("rls_matrix_runtime_flow", default=False)
_TABLE_TOKEN = r'(?:(?:"[^"]+")|(?:[A-Za-z_][A-Za-z0-9_]*))(?:\.(?:(?:"[^"]+")|(?:[A-Za-z_][A-Za-z0-9_]*)))?'
_READ_RE = re.compile(rf'\b(?:FROM|JOIN)\s+({_TABLE_TOKEN})', re.I)
_INSERT_RE = re.compile(rf'\bINSERT\s+INTO\s+({_TABLE_TOKEN})', re.I)
_UPDATE_RE = re.compile(rf'\bUPDATE\s+({_TABLE_TOKEN})', re.I)
_DELETE_RE = re.compile(rf'\bDELETE\s+FROM\s+({_TABLE_TOKEN})', re.I)
_SEQUENCE_RE = re.compile(r"\b(?:nextval|currval|setval)\s*\(\s*'([^']+)'", re.I)


def _clean_identifier(value):
    return value.replace('"', '').strip().rstrip(',;')


def _flow(test_id):
    parts = test_id.split('.')
    return '.'.join(parts[:2]) if len(parts) > 1 else test_id


class MatrixCollector:
    def __init__(self):
        self.rows = defaultdict(lambda: {"tests": set(), "aliases": set()})
        self.sequences = defaultdict(lambda: {"tests": set(), "aliases": set()})

    def __call__(self, execute, sql, params, many, context):
        statement = str(sql)
        executor = current_executor()
        if executor == "default" and not _ACTIVE_RUNTIME_FLOW.get():
            return execute(sql, params, many, context)
        test_id = _CURRENT_TEST.get()
        alias = context["connection"].alias
        writes = []
        for operation, regex in (
            ("INSERT", _INSERT_RE), ("UPDATE", _UPDATE_RE), ("DELETE", _DELETE_RE)
        ):
            for match in regex.finditer(statement):
                writes.append((operation, _clean_identifier(match.group(1))))
        for operation, table in writes:
            key = (executor, table, operation)
            self.rows[key]["tests"].add(test_id)
            self.rows[key]["aliases"].add(alias)
        for match in _READ_RE.finditer(statement):
            table = _clean_identifier(match.group(1))
            if table.startswith('('):
                continue
            key = (executor, table, "SELECT")
            self.rows[key]["tests"].add(test_id)
            self.rows[key]["aliases"].add(alias)
        for match in _SEQUENCE_RE.finditer(statement):
            function = statement[match.start():match.start()+12].lower()
            operation = "USAGE" if "nextval" in function else "SELECT"
            key = (executor, _clean_identifier(match.group(1)), operation)
            self.sequences[key]["tests"].add(test_id)
            self.sequences[key]["aliases"].add(alias)
        return execute(sql, params, many, context)

    def write(self):
        default_output = Path(__file__).resolve().parents[3] / "_auditoria_rls"
        output = Path(os.environ.get("BOTUKA_RLS_MATRIX_DIR", default_output))
        output.mkdir(parents=True, exist_ok=True)
        raw = []
        for (executor, table, operation), evidence in sorted(self.rows.items()):
            if table.lower().startswith(('pg_', 'information_schema.')):
                continue
            schema, _, name = table.partition('.')
            if not name:
                schema, name = 'public', schema
            raw.append({
                "executor": executor, "schema": schema, "table": name,
                "operation": operation, "flows": sorted({_flow(x) for x in evidence["tests"]}),
                "tests": sorted(evidence["tests"]), "connection_aliases": sorted(evidence["aliases"]),
            })
        (output / "observed_operations.json").write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        matrix = {}
        for row in raw:
            key = (row["executor"], row["schema"], row["table"])
            item = matrix.setdefault(key, {
                "role": {"default":"botuka_app","worker":"botuka_worker","internal":"botuka_internal","maintenance":"sawaya"}.get(row["executor"], row["executor"]),
                "executor": row["executor"], "schema": row["schema"], "table": row["table"],
                "SELECT":"NÃO", "INSERT":"NÃO", "UPDATE":"NÃO", "DELETE":"NÃO", "flows": set(),
            })
            if row["operation"] in item:
                item[row["operation"]] = "SIM"
            item["flows"].update(row["flows"])
        with (output / "privilege_matrix_observed.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            fields=["role","executor","schema","table","SELECT","INSERT","UPDATE","DELETE","flows"]
            writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader()
            for item in sorted(matrix.values(), key=lambda x:(x["role"],x["schema"],x["table"])):
                item=dict(item); item["flows"]=';'.join(sorted(item["flows"])); writer.writerow(item)
        seq=[]
        for (executor,name,operation), evidence in sorted(self.sequences.items()):
            seq.append({"executor":executor,"sequence":name,"operation":operation,"flows":sorted({_flow(x) for x in evidence["tests"]})})
        (output / "observed_sequences.json").write_text(json.dumps(seq,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"RLS_MATRIX_ROWS={len(matrix)} OUTPUT={output}")


_COLLECTOR = MatrixCollector()


class MatrixPhysicalRouter:
    """Mantém o executor lógico, usando somente o banco físico de teste."""

    def db_for_read(self, model, **hints): return "default"
    def db_for_write(self, model, **hints): return "default"
    def allow_relation(self, obj1, obj2, **hints): return True
    def allow_migrate(self, db, app_label, model_name=None, **hints): return db == "default"


class MatrixDatabaseExecutorMiddleware:
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        logical_alias = request_database_alias(request.path_info)
        request.database_alias = logical_alias
        with database_executor(logical_alias), transaction.atomic(using="default"):
            token = _ACTIVE_RUNTIME_FLOW.set(True)
            try:
                response = self.get_response(request)
            finally:
                _ACTIVE_RUNTIME_FLOW.reset(token)
            if getattr(response, "status_code", 200) >= 400:
                transaction.set_rollback(True, using="default")
            return response


class MatrixRLSUserContextMiddleware:
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        connection = connections["default"]
        with transaction.atomic(using="default"):
            user = getattr(request, "user", None)
            user_id = str(user.pk) if user is not None and user.is_authenticated else ""
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.user_id', %s, true)", [user_id])
            response = self.get_response(request)
            if getattr(response, "status_code", 200) >= 400:
                transaction.set_rollback(True, using="default")
            return response


class MatrixResult(TextTestResult):
    def startTest(self, test):
        self._matrix_token = _CURRENT_TEST.set(test.id())
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        _CURRENT_TEST.reset(self._matrix_token)


class MatrixTextRunner(TextTestRunner):
    resultclass = MatrixResult


class RLSMatrixTestRunner(DiscoverRunner):
    test_runner = MatrixTextRunner

    def run_suite(self, suite, **kwargs):
        database_name = str(connections["default"].settings_dict["NAME"])
        if not database_name.startswith("test_"):
            raise RuntimeError(f"Instrumentação bloqueada fora de banco de teste: {database_name}")
        with ExitStack() as stack:
            for alias in connections:
                stack.enter_context(connections[alias].execute_wrapper(_COLLECTOR))
            result = super().run_suite(suite, **kwargs)
        _COLLECTOR.write()
        return result
