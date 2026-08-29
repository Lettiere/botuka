from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.organizations.models import Empresa
from apps.painel.forms import EmpresaForm


class EmpresaAtuacaoFoundationTests(SimpleTestCase):
    def test_choices_representam_as_tres_atuacoes(self):
        self.assertEqual(
            set(Empresa.Atuacao.values),
            {'COMERCIO', 'SERVICOS', 'COMERCIO_E_SERVICOS'},
        )

    def test_campo_permite_null_para_compatibilidade_com_legado(self):
        field = Empresa._meta.get_field('atuacao')
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertFalse(field.has_default())

    def test_form_exige_atuacao_para_novos_envios(self):
        form = EmpresaForm()
        self.assertTrue(form.fields['atuacao'].required)

    def test_servicos_normaliza_modalidade_comercial(self):
        empresa = Empresa(
            atuacao=Empresa.Atuacao.SERVICOS,
            modalidade_comercial=Empresa.ModalidadeComercial.VAREJO,
        )

        empresa.clean()

        self.assertEqual(empresa.modalidade_comercial, '')

    def test_comercio_exige_modalidade_comercial(self):
        for atuacao in (
            Empresa.Atuacao.COMERCIO,
            Empresa.Atuacao.COMERCIO_E_SERVICOS,
        ):
            with self.subTest(atuacao=atuacao):
                empresa = Empresa(
                    atuacao=atuacao, modalidade_comercial='',
                    status=Empresa.Status.PENDENTE,
                )

                with self.assertRaises(ValidationError) as contexto:
                    empresa.clean()

                self.assertIn(
                    'modalidade_comercial',
                    contexto.exception.message_dict,
                )

    def test_registro_legado_sem_atuacao_permanece_compativel(self):
        empresa = Empresa(
            atuacao=None,
            modalidade_comercial=Empresa.ModalidadeComercial.ATACADO,
        )

        empresa.clean()
