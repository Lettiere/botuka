import csv
import hashlib
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.db import connection
from django.urls import reverse
from pathlib import Path

from apps.services.management.commands.importar_taxonomia_servicos import (
    EXPECTED_CONFIRMATION,
    validate_catalog,
)
from apps.painel.forms import ServicoForm
from apps.services.models import (
    AreaProfissional, FormaCobranca, Profissao, ProfissaoTipoServico,
    Servico, Setor, TipoServico,
)


class ServiceTaxonomyCatalogTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalog_tmp = TemporaryDirectory()
        cls.addClassCleanup(cls.catalog_tmp.cleanup)
        catalog_dir = Path(cls.catalog_tmp.name)

        sectors = [
            {
                'setor_slug': f'setor-{sector:02d}',
                'setor_nome': f'Setor {sector:02d}',
                'setor_ordem': str(sector),
            }
            for sector in range(1, 41)
        ]
        areas = [
            {
                'setor_slug': sector['setor_slug'],
                'area_slug': f"{sector['setor_slug']}-area-{area:02d}",
                'area_nome': f"Área {sector['setor_nome']} {area:02d}",
                'area_ordem': str(area),
            }
            for sector in sectors
            for area in range(1, 6)
        ]
        professions = [
            {
                'setor_slug': area['setor_slug'],
                'area_slug': area['area_slug'],
                'profissao_slug': f"{area['area_slug']}-profissao-{profession:02d}",
                'profissao_nome': f"Profissão {area['area_nome']} {profession:02d}",
            }
            for area in areas
            for profession in range(1, 9)
        ]

        def write_csv(name, rows):
            with (catalog_dir / name).open(
                'w', encoding='utf-8', newline=''
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

        write_csv('01_SETORES.csv', sectors)
        write_csv('02_AREAS_PROFISSIONAIS.csv', areas)
        write_csv('03_PROFISSOES.csv', professions)
        hierarchy = catalog_dir / '04_HIERARQUIA_COMPLETA.csv'
        hierarchy.write_text('fixture-taxonomia-servicos' + chr(10), encoding='utf-8')
        digest = hashlib.sha256(hierarchy.read_bytes()).hexdigest()
        (catalog_dir / '10_HASH_CATALOGO.txt').write_text(
            f'{digest}  04_HIERARQUIA_COMPLETA.csv' + chr(10), encoding='ascii'
        )

        cls.catalog_patch = patch(
            'apps.services.management.commands.importar_taxonomia_servicos.CATALOG_DIR',
            catalog_dir,
        )
        cls.catalog_patch.start()
        cls.addClassCleanup(cls.catalog_patch.stop)
    def test_catalogo_cumpre_metas_e_relacionamentos(self):
        setores, areas, profissoes, digest = validate_catalog()
        self.assertGreaterEqual(len(setores), 40)
        self.assertGreaterEqual(len(areas), 200)
        self.assertGreaterEqual(len(profissoes), 1500)
        self.assertEqual(len(digest), 64)

    def test_dry_run_faz_rollback_integral(self):
        before = (Setor.objects.count(), AreaProfissional.objects.count(), Profissao.objects.count())
        with connection.cursor() as cursor:
            cursor.execute("SELECT last_value,is_called FROM services.services_setor_tb_services_setor_id_seq")
            sequence_before = cursor.fetchone()
        call_command('importar_taxonomia_servicos', verbosity=0)
        self.assertEqual(
            (Setor.objects.count(), AreaProfissional.objects.count(), Profissao.objects.count()),
            before,
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT last_value,is_called FROM services.services_setor_tb_services_setor_id_seq")
            self.assertEqual(cursor.fetchone(), sequence_before)

    @override_settings(DEBUG=True)
    def test_aplicacao_e_idempotente(self):
        database = str(settings.DATABASES['default']['NAME'])
        options = {'apply': True, 'confirm': EXPECTED_CONFIRMATION, 'allow_database': database, 'verbosity': 0}
        call_command('importar_taxonomia_servicos', **options)
        first = (Setor.objects.count(), AreaProfissional.objects.count(), Profissao.objects.count())
        call_command('importar_taxonomia_servicos', **options)
        self.assertEqual((Setor.objects.count(), AreaProfissional.objects.count(), Profissao.objects.count()), first)
        self.assertGreaterEqual(first[0], 40)
        self.assertGreaterEqual(first[1], 200)
        self.assertGreaterEqual(first[2], 1500)

    def test_profissao_rejeita_area_de_outro_setor(self):
        setor_a = Setor.objects.create(nome='Setor A')
        setor_b = Setor.objects.create(nome='Setor B')
        area = AreaProfissional.objects.create(setor=setor_a, nome='Área A')
        with self.assertRaises(ValidationError):
            Profissao.objects.create(setor=setor_b, area=area, nome='Profissão inválida')


class ServiceTaxonomyEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        cls.user = get_user_model().objects.create_user('taxonomy-service-user')
        cls.setor = Setor.objects.create(nome='Tecnologia da Informação')
        cls.area = AreaProfissional.objects.create(setor=cls.setor, nome='Desenvolvimento')
        cls.profissao = Profissao.objects.create(setor=cls.setor, area=cls.area, nome='Desenvolvedor')
        cls.tipo = TipoServico.objects.create(nome='Desenvolvimento de software')
        cls.forma = FormaCobranca.objects.create(nome='Por projeto')
        ProfissaoTipoServico.objects.create(profissao=cls.profissao, tipo_servico=cls.tipo)

    def setUp(self):
        self.client.force_login(self.user)

    def test_endpoints_busca_e_hierarquia_estrita(self):
        setores = self.client.get(reverse('painel:servicos_ajax_setores'), {'q': 'Tecnologia'})
        areas = self.client.get(reverse('painel:servicos_ajax_areas'), {'setor_id': self.setor.pk, 'q': 'Desenvol'})
        profissoes = self.client.get(reverse('painel:servicos_ajax_profissoes'), {'area_profissional_id': self.area.pk, 'q': 'Desenvol'})
        tipos = self.client.get(reverse('painel:servicos_ajax_tipos'), {'profissao_id': self.profissao.pk})
        self.assertEqual(setores.json()['results'][0]['id'], self.setor.pk)
        self.assertEqual(areas.json()['results'][0]['id'], self.area.pk)
        self.assertEqual(profissoes.json()['results'][0]['id'], self.profissao.pk)
        self.assertEqual(tipos.json()['results'][0]['id'], self.tipo.pk)

    def test_endpoints_sem_parametro_retornam_lista_vazia(self):
        for url_name in ('servicos_ajax_areas', 'servicos_ajax_profissoes', 'servicos_ajax_tipos'):
            response = self.client.get(reverse(f'painel:{url_name}'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'results': []})

    def test_endpoints_com_ids_invalidos_retornam_lista_vazia(self):
        casos = (
            ('servicos_ajax_areas', {'setor_id': 'invalido'}),
            ('servicos_ajax_profissoes', {'area_profissional_id': '999999999'}),
            ('servicos_ajax_tipos', {'profissao_id': 'invalido'}),
        )
        for url_name, params in casos:
            response = self.client.get(reverse(f'painel:{url_name}'), params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'results': []})

    def test_endpoint_tipos_retorna_vazio_para_profissao_sem_vinculo(self):
        profissao = Profissao.objects.create(
            setor=self.setor, area=self.area, nome='Profissão sem tipo',
        )
        response = self.client.get(
            reverse('painel:servicos_ajax_tipos'), {'profissao_id': profissao.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'results': []})

    def test_endpoints_nao_retornam_registros_inativos_ou_de_outro_pai(self):
        outro_setor = Setor.objects.create(nome='Outro setor')
        outra_area = AreaProfissional.objects.create(setor=outro_setor, nome='Outra área')
        outra_profissao = Profissao.objects.create(setor=outro_setor, area=outra_area, nome='Outra profissão')
        outro_tipo = TipoServico.objects.create(nome='Outro tipo')
        ProfissaoTipoServico.objects.create(profissao=outra_profissao, tipo_servico=outro_tipo)
        AreaProfissional.objects.create(setor=self.setor, nome='Área inativa', ativo=False)
        Profissao.objects.create(setor=self.setor, area=self.area, nome='Profissão inativa', ativo=False)
        tipo_inativo = TipoServico.objects.create(nome='Tipo inativo', ativo=False)
        ProfissaoTipoServico.objects.create(profissao=self.profissao, tipo_servico=tipo_inativo)
        self.assertEqual(
            self.client.get(reverse('painel:servicos_ajax_areas'), {'setor_id': self.setor.pk}).json()['results'],
            [{'id': self.area.pk, 'text': self.area.nome}],
        )
        self.assertEqual(
            self.client.get(reverse('painel:servicos_ajax_profissoes'), {'area_profissional_id': self.area.pk}).json()['results'],
            [{'id': self.profissao.pk, 'text': self.profissao.nome}],
        )
        self.assertEqual(
            self.client.get(reverse('painel:servicos_ajax_tipos'), {'profissao_id': self.profissao.pk}).json()['results'],
            [{'id': self.tipo.pk, 'text': self.tipo.nome}],
        )

    def test_endpoints_exigem_a_mesma_autenticacao_do_formulario(self):
        self.client.logout()
        for url_name in ('servico_criar', 'servicos_ajax_areas', 'servicos_ajax_profissoes', 'servicos_ajax_tipos'):
            self.assertEqual(self.client.get(reverse(f'painel:{url_name}')).status_code, 302)

    def _form_data(self, **overrides):
        data = {
            'prestador_tipo': Servico.PrestadorTipo.PESSOA_FISICA,
            'setor': self.setor.pk,
            'area': self.area.pk,
            'profissao': self.profissao.pk,
            'tipo_servico': self.tipo.pk,
            'forma_cobranca': self.forma.pk,
            'titulo': 'Criação válida pelos selects dependentes',
            'atendimento_presencial': 'on',
        }
        data.update(overrides)
        return data

    def test_formulario_rejeita_tipo_de_outra_profissao(self):
        outra_profissao = Profissao.objects.create(setor=self.setor, area=self.area, nome='Analista')
        outro_tipo = TipoServico.objects.create(nome='Análise especializada')
        ProfissaoTipoServico.objects.create(profissao=outra_profissao, tipo_servico=outro_tipo)
        form = ServicoForm(self._form_data(tipo_servico=outro_tipo.pk), usuario=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('não pertence à profissão', ' '.join(form.errors['tipo_servico']))

    def test_formulario_rejeita_profissao_de_outra_area(self):
        outra_area = AreaProfissional.objects.create(setor=self.setor, nome='Outra área válida')
        outra_profissao = Profissao.objects.create(
            setor=self.setor, area=outra_area, nome='Profissão de outra área',
        )
        outro_tipo = TipoServico.objects.create(nome='Tipo da outra área')
        ProfissaoTipoServico.objects.create(profissao=outra_profissao, tipo_servico=outro_tipo)
        form = ServicoForm(
            self._form_data(profissao=outra_profissao.pk, tipo_servico=outro_tipo.pk),
            usuario=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('não pertence à área', ' '.join(form.errors['profissao']))

    def test_criacao_valida_e_edicao_preservam_encadeamento(self):
        form = ServicoForm(self._form_data(), usuario=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        servico = form.save()
        edit_form = ServicoForm(instance=servico, usuario=self.user)
        self.assertEqual(edit_form['setor'].value(), self.setor.pk)
        self.assertEqual(edit_form['area'].value(), self.area.pk)
        self.assertEqual(edit_form['profissao'].value(), self.profissao.pk)
        self.assertEqual(edit_form['tipo_servico'].value(), self.tipo.pk)
        self.assertIn(self.tipo, edit_form.fields['tipo_servico'].queryset)

    def test_formulario_carrega_select2(self):
        response = self.client.get(reverse('painel:servico_criar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'select2.min.js')
        self.assertContains(response, 'name="area"', html=False)
        self.assertContains(response, 'id="id_setor"', html=False)
        self.assertContains(response, 'id="id_area"', html=False)
        self.assertContains(response, 'id="id_profissao"', html=False)
        self.assertContains(response, 'id="id_tipo_servico"', html=False)
        self.assertContains(response, 'data-areas-url="/painel/servicos/ajax/areas/"', html=False)
        self.assertContains(response, 'data-profissoes-url="/painel/servicos/ajax/profissoes/"', html=False)
        self.assertContains(response, 'data-tipos-url="/painel/servicos/ajax/tipos/"', html=False)
        for field_id in ('id_setor', 'id_area', 'id_profissao', 'id_tipo_servico'):
            self.assertEqual(response.content.count(f'id="{field_id}"'.encode()), 1)
        self.assertEqual(response.content.count(b'data-dependency-status="area"'), 1)

    def test_javascript_registra_eventos_diretos_e_sincroniza_select2(self):
        script = (
            Path(settings.BASE_DIR) / 'static' / 'painel' / 'js' / 'servicos.js'
        ).read_text(encoding='utf-8')
        self.assertIn("setorSelect.addEventListener('change'", script)
        self.assertIn("areaSelect.addEventListener('change'", script)
        self.assertIn("profissaoSelect.addEventListener('change'", script)
        self.assertIn('?setor_id=', script)
        self.assertIn('?area_profissional_id=', script)
        self.assertIn('?profissao_id=', script)
        self.assertIn(".prop('disabled', disabled).trigger('change.select2')", script)
        self.assertIn('Nenhum tipo de serviço cadastrado para esta profissão', script)
