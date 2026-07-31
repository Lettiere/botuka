from django.test import SimpleTestCase

from apps.core.management.commands.audit_local_public_urls import (
    normalize_legacy_local_url,
)


class LegacyPublicUrlNormalizationTests(SimpleTestCase):
    def test_extrai_path_query_e_fragmento_de_url_local(self):
        self.assertEqual(
            normalize_legacy_local_url(
                "http://127.0.0.1:7700/empresas/aleicah/?origem=qr#contato"
            ),
            "/empresas/aleicah/?origem=qr#contato",
        )

    def test_nao_altera_dominio_externo(self):
        self.assertIsNone(
            normalize_legacy_local_url("https://botuka.com.br/empresas/aleicah/")
        )
