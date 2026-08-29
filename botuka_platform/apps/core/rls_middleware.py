from django.db import connection, transaction


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
        if (
            connection.vendor == "postgresql"
            and connection.in_atomic_block
        ):
            transaction.set_rollback(True)

        return None

    def __call__(self, request):
        if connection.vendor != "postgresql":
            return self.get_response(request)

        with transaction.atomic():
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
                transaction.set_rollback(True)

            return response
