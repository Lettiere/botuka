from contextlib import contextmanager

from django.db import connection, transaction


@contextmanager
def rls_user_context(user_id):
    """
    Contexto PostgreSQL app.user_id restrito à transação atual.

    Destinado a operações fora do middleware HTTP, como WebSockets.
    """

    if connection.vendor != "postgresql":
        yield
        return

    value = str(user_id) if user_id is not None else ""

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.user_id', %s, true)",
                [value],
            )

        yield
