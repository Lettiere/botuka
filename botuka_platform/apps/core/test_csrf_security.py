from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.middleware.csrf import rotate_token
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from config.settings import cast_debug


class CsrfRequestTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.login_url = reverse('accounts:login')

    def _token(self, *, host='127.0.0.1:7700', secure=False):
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            self.client.get(reverse('home'), HTTP_HOST=host, secure=secure)
        return self.client.cookies['csrftoken'].value

    def test_local_post_with_valid_token_works(self):
        token = self._token()
        with patch('apps.accounts.views.authenticate', return_value=None):
            response = self.client.post(
                self.login_url,
                {'email': 'missing@example.com', 'password': 'invalid', 'csrfmiddlewaretoken': token},
                HTTP_HOST='127.0.0.1:7700',
                HTTP_ORIGIN='http://127.0.0.1:7700',
            )
        self.assertEqual(response.status_code, 302)

    @override_settings(ALLOWED_HOSTS=['botuka.com.br'])
    def test_online_post_with_valid_token_works(self):
        token = self._token(host='botuka.com.br', secure=True)
        with patch('apps.accounts.views.authenticate', return_value=None):
            response = self.client.post(
                self.login_url,
                {'email': 'missing@example.com', 'password': 'invalid', 'csrfmiddlewaretoken': token},
                HTTP_HOST='botuka.com.br',
                HTTP_ORIGIN='https://botuka.com.br',
                secure=True,
            )
        self.assertEqual(response.status_code, 302)

    def test_missing_and_incorrect_tokens_return_friendly_403(self):
        missing = self.client.post(self.login_url, HTTP_HOST='127.0.0.1:7700')
        self.assertEqual(missing.status_code, 403)
        self.assertContains(missing, 'Sua sessão ou formulário expirou', status_code=403)
        self.assertNotContains(missing, 'CSRF token from POST incorrect', status_code=403)

        self._token()
        incorrect = self.client.post(
            self.login_url,
            {'csrfmiddlewaretoken': 'x' * 64},
            HTTP_HOST='127.0.0.1:7700',
        )
        self.assertEqual(incorrect.status_code, 403)

    def test_login_rotates_csrf_token_and_logout_requires_post_csrf(self):
        user = SimpleNamespace(email='csrf@example.com', is_authenticated=True)
        old_token = self._token()
        with (
            patch('apps.accounts.views.authenticate', return_value=user),
            patch('apps.accounts.views.login', side_effect=lambda request, _: rotate_token(request)),
        ):
            response = self.client.post(
                self.login_url,
                {
                    'email': user.email,
                    'password': 'safe-password-123',
                    'csrfmiddlewaretoken': old_token,
                    'next': '/painel/',
                },
                HTTP_HOST='127.0.0.1:7700',
            )
        self.assertEqual(response.status_code, 302)
        new_token = self.client.cookies['csrftoken'].value
        self.assertNotEqual(old_token, new_token)

        logout_url = reverse('accounts:logout')
        self.assertEqual(self.client.get(logout_url, HTTP_HOST='127.0.0.1:7700').status_code, 405)
        self.assertEqual(self.client.post(logout_url, HTTP_HOST='127.0.0.1:7700').status_code, 403)
        with patch('apps.accounts.views.logout'):
            response = self.client.post(
                logout_url,
                {'csrfmiddlewaretoken': new_token},
                HTTP_HOST='127.0.0.1:7700',
            )
        self.assertEqual(response.status_code, 302)


class CsrfConfigurationTests(SimpleTestCase):
    def test_debug_parser_handles_false_strings_safely(self):
        for value in ('False', 'false', '0', 'no', 'off', 'production'):
            self.assertFalse(cast_debug(value))
        for value in ('True', 'true', '1', 'yes', 'on', 'development'):
            self.assertTrue(cast_debug(value))

    def test_official_origins_and_middleware_are_configured(self):
        self.assertIn('django.middleware.csrf.CsrfViewMiddleware', settings.MIDDLEWARE)
        self.assertIn('https://botuka.com.br', settings.CSRF_TRUSTED_ORIGINS)
        self.assertIn('https://www.botuka.com.br', settings.CSRF_TRUSTED_ORIGINS)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')

    @override_settings(SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'))
    def test_https_proxy_header_is_recognized(self):
        request = RequestFactory().get('/', HTTP_X_FORWARDED_PROTO='https')
        self.assertTrue(request.is_secure())

    def test_environment_examples_document_local_cookie_policy(self):
        env_example = (settings.BASE_DIR.parent / '.env.example').read_text(encoding='utf-8')
        self.assertIn('CSRF_COOKIE_SECURE=False', env_example)
        self.assertIn('SESSION_COOKIE_SECURE=False', env_example)
        self.assertIn('USE_PROXY_SSL_HEADER=False', env_example)

    def test_important_post_templates_contain_csrf_token(self):
        groups = {
            'empresa': ['painel/empresas/form.html'],
            'servico': ['painel/servicos/form.html', 'painel/servicos/novo.html'],
            'curriculo': ['painel/curriculo/etapa.html', 'painel/curriculo/itens.html'],
            'vaga': ['painel/recruitment/form.html'],
        }
        for label, relative_paths in groups.items():
            for relative_path in relative_paths:
                content = (settings.BASE_DIR / 'templates' / relative_path).read_text(encoding='utf-8')
                self.assertIn('{% csrf_token %}', content, f'Token ausente em {label}: {relative_path}')

    def test_internal_views_do_not_use_csrf_exempt(self):
        apps_dir = settings.BASE_DIR / 'apps'
        offenders = []
        for path in apps_dir.rglob('views.py'):
            if 'csrf_exempt' in path.read_text(encoding='utf-8'):
                offenders.append(str(path.relative_to(settings.BASE_DIR)))
        self.assertEqual(offenders, [])
