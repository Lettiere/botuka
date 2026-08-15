from django.template import Context, Template
from django.test import SimpleTestCase

from apps.core.services.contacts import formatar_telefone, telefone_para_whatsapp
from apps.core.services.rich_text import sanitizar_html_rico
from apps.painel.forms import EmpresaForm


class CompanyPublicContentTests(SimpleTestCase):
    def test_rich_text_removes_active_content_and_unsafe_attributes(self):
        value = (
            '<h2 onclick="alert(1)">Título</h2><script>alert(2)</script>'
            '<a href="javascript:alert(3)" style="color:red">ruim</a>'
            '<a href="https://example.com" title="Saiba mais" target="_blank">ok</a>'
        )
        result = sanitizar_html_rico(value)
        self.assertNotIn('script', result)
        self.assertNotIn('onclick', result)
        self.assertNotIn('javascript:', result)
        self.assertNotIn('style=', result)
        self.assertIn('href="https://example.com"', result)
        self.assertIn('title="Saiba mais"', result)
        self.assertIn('rel="noopener noreferrer"', result)

    def test_legacy_plain_text_is_rendered_as_paragraphs(self):
        rendered = Template(
            '{% load content_tags %}{{ value|richtext }}'
        ).render(Context({
            'value': 'Primeira linha' + chr(10) * 2 + 'Segunda linha',
        }))
        self.assertIn('<p>Primeira linha</p>', rendered)
        self.assertIn('<p>Segunda linha</p>', rendered)

    def test_brazilian_contacts_are_formatted_and_whatsapp_is_international(self):
        self.assertEqual(formatar_telefone('11998263095'), '(11) 99826-3095')
        self.assertEqual(
            telefone_para_whatsapp('11998263095'),
            'https://wa.me/5511998263095',
        )

    def test_company_description_widget_is_connected_to_existing_editor(self):
        field = EmpresaForm().fields['descricao_completa']
        self.assertIn('data-richtext-source', field.widget.attrs)
