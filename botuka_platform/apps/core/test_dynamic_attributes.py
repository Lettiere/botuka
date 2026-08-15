from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.attribute_forms import atributo_formset
from apps.core.models import AtributoAdicional
from apps.core.search import GlobalSearchService
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Empresa
from apps.recruitment.models import Vaga
from apps.services.models import FormaCobranca, Profissao, Servico, Setor


class DynamicAttributesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user('attribute-owner', password='safe-pass')
        cls.other = users.objects.create_user('attribute-other', password='safe-pass')
        pais = Pais.objects.create(nome='Brasil Atributos', codigo_iso_2='AT', codigo_iso_3='ATR')
        estado = Estado.objects.create(pais=pais, nome='São Paulo Atributos', sigla='AZ')
        cidade = Cidade.objects.create(estado=estado, nome='Botucatu Atributos')
        cls.company = Empresa.objects.create(
            usuario_proprietario=cls.owner, nome_fantasia='Empresa Atributos',
            cidade=cidade, estado=estado, status=Empresa.Status.ATIVA,
            ativo=True, perfil_publico=True,
        )
        setor = Setor.objects.create(nome='Transportes Atributos')
        profissao = Profissao.objects.create(setor=setor, nome='Motorista Atributos')
        cobranca = FormaCobranca.objects.create(nome='Por viagem atributos')
        cls.service = Servico.objects.create(
            usuario_responsavel=cls.owner,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=setor, profissao=profissao, forma_cobranca=cobranca,
            titulo='Motorista executivo', descricao_curta='Transporte profissional',
            status=Servico.Status.PUBLICADO, ativo=True, publicado_em=timezone.now(),
        )
        cls.job = Vaga(
            empresa=cls.company, usuario_criador=cls.owner, usuario_responsavel=cls.owner,
            titulo='Motorista particular', slug='motorista-particular-atributos',
            descricao='Vaga para transporte executivo', tipo_contrato='CLT',
            modalidade='PRESENCIAL', cidade='Botucatu', estado='SP',
            status=Vaga.Status.PUBLICADA, publicado_em=timezone.now(),
        )
        Vaga.objects.bulk_create([cls.job])

    def create_attribute(self, target, **overrides):
        values = {
            'tipo': AtributoAdicional.Tipo.EXPERIENCIA,
            'valor': 'Direção defensiva',
            'classificacao': (
                AtributoAdicional.Classificacao.OBRIGATORIO
                if isinstance(target, Vaga)
                else AtributoAdicional.Classificacao.CARACTERISTICA
            ),
        }
        values.update(overrides)
        values['vaga' if isinstance(target, Vaga) else 'servico'] = target
        return AtributoAdicional.objects.create(**values)

    def test_job_and_service_accept_repeated_ordered_attributes(self):
        first = self.create_attribute(self.job, ordem=2)
        second = self.create_attribute(
            self.job, valor='Experiência com Uber',
            classificacao=AtributoAdicional.Classificacao.DESEJAVEL, ordem=1,
        )
        service_item = self.create_attribute(self.service, valor='5 anos', ordem=1)
        self.assertEqual(
            list(self.job.atributos_adicionais.values_list('pk', flat=True)),
            [second.pk, first.pk],
        )
        self.assertEqual(service_item.servico, self.service)

    def test_custom_type_validation_and_html_removal(self):
        with self.assertRaises(ValidationError):
            self.create_attribute(
                self.job, tipo=AtributoAdicional.Tipo.OUTRO,
                nome_personalizado='', valor='Sim',
            )
        item = self.create_attribute(
            self.service, tipo=AtributoAdicional.Tipo.OUTRO,
            nome_personalizado='<b>Possui EAR</b>', valor='<script>x</script>Sim',
        )
        self.assertEqual(item.nome_personalizado, 'Possui EAR')
        self.assertEqual(item.valor, 'xSim')

    def test_shared_formset_edits_removes_and_reorders(self):
        existing = self.create_attribute(self.service)
        data = {
            'atributos-TOTAL_FORMS': '2', 'atributos-INITIAL_FORMS': '1',
            'atributos-MIN_NUM_FORMS': '0', 'atributos-MAX_NUM_FORMS': '1000',
            'atributos-0-id': str(existing.pk), 'atributos-0-tipo': 'EXPERIENCIA',
            'atributos-0-valor': 'Direção defensiva', 'atributos-0-classificacao': 'CARACTERISTICA',
            'atributos-0-observacao': '', 'atributos-0-ordem': '0', 'atributos-0-DELETE': 'on',
            'atributos-1-id': '', 'atributos-1-tipo': 'EXPERIENCIA',
            'atributos-1-valor': 'Transporte executivo', 'atributos-1-classificacao': 'DIFERENCIAL',
            'atributos-1-observacao': '', 'atributos-1-ordem': '3',
        }
        formset = atributo_formset('servico', instance=self.service, data=data)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual(
            list(self.service.atributos_adicionais.values_list('valor', 'ordem')),
            [('Transporte executivo', 3)],
        )

    def test_attributes_participate_in_global_and_directory_search(self):
        self.create_attribute(self.job)
        self.create_attribute(self.service)
        results, _ = GlobalSearchService().search('direção defensiva')
        kinds = {item.kind for item in results}
        self.assertTrue({'vagas', 'servicos'}.issubset(kinds))
        self.assertContains(self.client.get(reverse('recruitment_public:vagas'), {'q': 'defensiva'}), self.job.titulo)
        self.assertContains(self.client.get(reverse('publico:servicos'), {'q': 'defensiva'}), self.service.titulo)

    def test_public_details_cards_legacy_compatibility_and_permissions(self):
        for index in range(4):
            self.create_attribute(self.job, valor=f'Requisito {index}', ordem=index)
            self.create_attribute(self.service, valor=f'Característica {index}', ordem=index)
        job_detail = self.client.get(reverse('recruitment_public:vaga', args=[self.job.slug]))
        service_detail = self.client.get(reverse('publico:servico', args=[self.service.slug]))
        self.assertContains(job_detail, 'Requisitos adicionais')
        self.assertContains(service_detail, 'Características do serviço')
        self.assertContains(self.client.get(reverse('recruitment_public:vagas')), '+1 informações')
        self.assertContains(self.client.get(reverse('publico:servicos')), '+1 informações')
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse('painel:vaga_editar', args=[self.job.uuid])).status_code,
            404,
        )
