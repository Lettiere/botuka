from django.db import connections, transaction

from .db_routing import database_executor


INTERNAL_PREFIXES = ("/admin/", "/gestao/")


def request_database_alias(path):
    normalized = path if path.endswith("/") else f"{path}/"
    if any(normalized.startswith(prefix) for prefix in INTERNAL_PREFIXES):
        return "internal"
    return "default"


class DatabaseExecutorMiddleware:
    """Seleciona e transaciona o executor antes de Session/Auth acessarem o ORM."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        alias = request_database_alias(request.path_info)
        request.database_alias = alias

        with database_executor(alias):
            connection = connections[alias]
            if connection.vendor != "postgresql":
                return self.get_response(request)

            with transaction.atomic(using=alias):
                response = self.get_response(request)
                if getattr(response, "status_code", 200) >= 400:
                    transaction.set_rollback(True, using=alias)
                return response
