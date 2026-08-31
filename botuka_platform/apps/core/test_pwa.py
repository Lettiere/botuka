from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse


class PwaIntegrationTests(TestCase):
    def test_home_contains_install_prompt_but_public_inner_page_does_not(self):
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            home = self.client.get(reverse('home'))
        self.assertContains(home, 'data-pwa-install-prompt')
        self.assertContains(home, 'Instalar agora')

        offline = self.client.get(reverse('offline'))
        self.assertNotContains(offline, 'data-pwa-install-prompt')

    def test_manifest_has_installable_and_maskable_png_icons(self):
        response = self.client.get(reverse('pwa_manifest'))
        self.assertEqual(response.status_code, 200)
        manifest = response.json()
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(manifest['start_url'], '/')
        self.assertTrue(any(icon['sizes'] == '192x192' for icon in manifest['icons']))
        self.assertTrue(any(icon['sizes'] == '512x512' for icon in manifest['icons']))
        self.assertTrue(any(icon['purpose'] == 'maskable' for icon in manifest['icons']))

    def test_manifest_icon_files_exist(self):
        icon_root = Path(settings.BASE_DIR) / 'static' / 'img' / 'icons'
        for filename in (
            'botuka-icon-180.png', 'botuka-icon-192.png',
            'botuka-icon-512.png', 'botuka-maskable-512.png',
        ):
            with self.subTest(filename=filename):
                self.assertTrue((icon_root / filename).is_file())

    def test_service_worker_has_offline_private_route_and_update_rules(self):
        response = self.client.get(reverse('service_worker'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        self.assertContains(response, '/offline/')
        self.assertContains(response, '/painel/')
        self.assertContains(response, '/conta/')
        self.assertContains(response, '/qrcode/')
        self.assertContains(response, '/compartilhar/')
        self.assertContains(response, 'SKIP_WAITING')
        self.assertContains(response, 'botuka-pwa-')
        self.assertContains(response, 'BOTUKA_RUNTIME_CACHE')
        self.assertContains(response, 'clients.claim()')
        self.assertContains(response, '/meus-agendamentos/')
        self.assertNotContains(response, '.then(() => self.skipWaiting())')

    @override_settings(PWA_VERSION='release-test-42')
    def test_service_worker_uses_release_version_and_removes_old_caches(self):
        response = self.client.get(reverse('service_worker'))
        self.assertContains(response, r'release\u002Dtest\u002D42')
        self.assertContains(response, 'cacheName.startsWith(BOTUKA_CACHE_PREFIX)')
        self.assertEqual(
            response['Cache-Control'], 'no-cache, no-store, must-revalidate'
        )

    @override_settings(PWA_VERSION='')
    def test_service_worker_calculates_stable_version_from_app_shell(self):
        first = self.client.get(reverse('service_worker')).content
        second = self.client.get(reverse('service_worker')).content
        self.assertEqual(first, second)
        self.assertNotIn(b'BOTUKA_CACHE_VERSION = ""', first)

    def test_pwa_script_limits_prompt_to_android_and_persists_choices(self):
        script = (
            Path(settings.BASE_DIR) / 'static' / 'js' / 'platform' / 'pwa.js'
        ).read_text(encoding='utf-8')
        self.assertIn('beforeinstallprompt', script)
        self.assertIn('/Android/i', script)
        self.assertIn("status: 'dismissed'", script)
        self.assertIn("status: 'installed'", script)
        self.assertIn('display-mode: standalone', script)
        self.assertIn('window.navigator.standalone', script)
        self.assertIn("registration.addEventListener('updatefound'", script)
        self.assertIn("navigator.serviceWorker.addEventListener('controllerchange'", script)
        self.assertIn("postMessage({type: 'SKIP_WAITING'})", script)
        self.assertIn('UPDATE_RELOAD_KEY', script)

    def test_update_notice_has_expected_copy_and_action(self):
        template = (
            Path(settings.BASE_DIR) / 'templates' / 'pwa' / 'register.html'
        ).read_text(encoding='utf-8')
        self.assertIn('Nova versão disponível', template)
        self.assertIn('Atualizar agora', template)
        self.assertIn('data-pwa-update', template)


class ConsentUiTests(SimpleTestCase):
    def test_consent_template_has_no_persistent_floating_review_button(self):
        template = (
            Path(settings.BASE_DIR) / 'templates' / 'seo' / 'consent.html'
        ).read_text(encoding='utf-8')
        self.assertNotIn('data-consent-review', template)
        self.assertIn('data-policy-version', template)

    def test_consent_script_hides_panel_and_validates_policy_version(self):
        script = (
            Path(settings.BASE_DIR) / 'static' / 'js' / 'platform' / 'consent.js'
        ).read_text(encoding='utf-8')
        self.assertIn('hideCompletely', script)
        self.assertIn("panel.hidden = true", script)
        self.assertIn('value.version !== policyVersion', script)
        self.assertIn('expiresAt', script)
