class PaymentWebhookCsrfBypassMiddleware:
    """CSRF is replaced by provider signature validation on exact webhook paths."""

    PREFIX = '/api/payments/webhooks/'
    ALLOWED = {'mercadopago/', 'c6/'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.PREFIX):
            suffix = request.path.removeprefix(self.PREFIX)
            if suffix in self.ALLOWED:
                request._dont_enforce_csrf_checks = True
        return self.get_response(request)
