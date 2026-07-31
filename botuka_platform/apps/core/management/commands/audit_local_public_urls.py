"""Audita e, opcionalmente, normaliza URLs locais persistidas."""

import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.db.models import Q


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
MARKERS = ("127.0.0.1", "localhost", ":7700")
URL_FIELD_HINTS = ("url", "link", "destino", "target", "short", "canonical")


def normalize_legacy_local_url(value):
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_HOSTS:
        return None
    return urlunsplit(("", "", parsed.path or "/", parsed.query, parsed.fragment))


class Command(BaseCommand):
    help = (
        "Localiza URLs absolutas locais em campos textuais. Por padrão é "
        "somente leitura; --apply exige --report e salva apenas o path."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--report", type=Path)

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        report_path = options["report"]
        if apply_changes and not report_path:
            raise CommandError("--apply exige --report para preservar o estado anterior.")

        findings = []
        for model in apps.get_models():
            fields = [
                field
                for field in model._meta.concrete_fields
                if isinstance(field, (models.CharField, models.TextField))
            ]
            if not fields:
                continue
            query = Q()
            for field in fields:
                for marker in MARKERS:
                    query |= Q(**{f"{field.name}__icontains": marker})
            if not query:
                continue
            try:
                rows = model._base_manager.filter(query).values(
                    model._meta.pk.name, *(field.name for field in fields)
                )
                for row in rows.iterator():
                    for field in fields:
                        old_value = row.get(field.name)
                        if not old_value or not any(marker in str(old_value).lower() for marker in MARKERS):
                            continue
                        is_url_field = isinstance(field, models.URLField) or any(
                            hint in field.name.lower() for hint in URL_FIELD_HINTS
                        )
                        findings.append(
                            {
                                "model": model._meta.label,
                                "table": model._meta.db_table,
                                "pk": str(row[model._meta.pk.name]),
                                "field": field.name,
                                "old": str(old_value),
                                "new": (
                                    normalize_legacy_local_url(old_value)
                                    if is_url_field
                                    else None
                                ),
                            }
                        )
            except Exception as exc:
                self.stderr.write(f"{model._meta.label}: auditoria ignorada ({exc})")

        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(findings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        correctable = [item for item in findings if item["new"]]
        if apply_changes:
            with transaction.atomic():
                for item in correctable:
                    model = apps.get_model(item["model"])
                    model._base_manager.filter(pk=item["pk"]).update(
                        **{item["field"]: item["new"]}
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Ocorrências: {len(findings)}; normalizáveis: {len(correctable)}; "
                f"alteradas: {len(correctable) if apply_changes else 0}."
            )
        )
        for item in findings:
            destination = item["new"] or "revisão manual"
            self.stdout.write(
                f"{item['model']} pk={item['pk']} campo={item['field']} -> {destination}"
            )
