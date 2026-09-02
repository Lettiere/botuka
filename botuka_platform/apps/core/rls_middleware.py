from django.core.exceptions import PermissionDenied
from django.db import connections, transaction
from django.http import Http404

from .db_routing import current_executor


class RLSUserContextMiddleware:
    """
    Contexto PostgreSQL app.user_id restrito à transação HTTP.

    - identidade vem exclusivamente de request.user;
    - usa SET LOCAL;
    - nunca usa contexto de sessão;
    - exceções e respostas HTTP >= 400 provocam rollback.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def process_exception(self, request, exception):
        # Deixe o Django renderizar respostas esperadas antes de marcar o
        # rollback. O status >= 400 fará isso ao final de __call__.
        if isinstance(exception, (Http404, PermissionDenied)):
            return None

        if (
            connections[current_executor()].vendor == "postgresql"
            and connections[current_executor()].in_atomic_block
        ):
            transaction.set_rollback(True, using=current_executor())

        return None

    def __call__(self, request):
        alias = current_executor()
        connection = connections[alias]
        if connection.vendor != "postgresql":
            return self.get_response(request)

        with transaction.atomic(using=alias):
            user = getattr(request, "user", None)

            user_id = (
                str(user.pk)
                if user is not None and user.is_authenticated
                else ""
            )

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.user_id', %s, true)",
                    [user_id],
                )

            response = self.get_response(request)

            if getattr(response, "status_code", 200) >= 400:
                transaction.set_rollback(True, using=alias)

            return response
