from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import AuditoriaPermissao, ConcessaoPermissao, Usuario
from apps.accounts.permission_services import conceder_permissao, revogar_permissao
from apps.core.models import Permissao

from .models import (
    CategoriaTurismo, ContatoTurismo, ExperienciaTuristica, GuiaTuristico,
    LocalTuristico, LocalizacaoVisibilidade, RedeSocialTurismo, RoteiroTuristico,
    EstruturaTurismo, ServicoTurismo, TurismoFoto, TurismoPlaylist,
    TurismoStatus, TurismoVideo, youtube_id,
)
from .forms import (
    ContatoTurismoForm, LocalInformacoesForm, LocalLocalizacaoForm,
    LocalRelacoesForm, LocalTuristicoForm,
)


class TourismSecurityTests(TestCase):
    def setUp(self):
        self.master = Usuario.objects.create_superuser('master-tourism', 'master-tourism@example.com', 'x')
        self.owner = Usuario.objects.create_user('owner-tourism', 'owner-tourism@example.com', 'x')
        self.other = Usuario.objects.create_user('other-tourism', 'other-tourism@example.com', 'x')
        self.permissions = {}
        for code in (
            'TURISMO_LOCAL_VISUALIZAR_PAINEL', 'TURISMO_LOCAL_CADASTRAR',
            'TURISMO_LOCAL_EDITAR_PROPRIOS', 'TURISMO_LOCAL_EDITAR_TODOS',
            'TURISMO_LOCAL_ENVIAR_ANALISE', 'TURISMO_LOCAL_PUBLICAR',
        ):
            self.permissions[code], _ = Permissao.objects.get_or_create(
                codigo=code,
                defaults={'modulo': 'Turismo', 'grupo': 'Local', 'nome': code},
            )

    def grant(self, user, code):
        return ConcessaoPermissao.objects.create(
            usuario=user, permissao=self.permissions[code],
            concedida_por=self.master, justificativa='Teste automatizado',
        )

    def local(self, owner=None, **kwargs):
        owner = owner or self.owner
        categoria, _ = CategoriaTurismo.objects.get_or_create(
            slug='natureza-teste', defaults={'nome': 'Natureza'},
        )
        return LocalTuristico.objects.create(
            nome=kwargs.pop('nome', 'Mirante'), slug=kwargs.pop('slug', 'mirante'),
            categoria=categoria, descricao_curta='Vista da Cuesta',
            descricao_completa='Descrição pública', usuario_criador=owner,
            usuario_atualizador=owner, **kwargs,
        )

    def test_usuario_sem_permissao_recebe_403(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('painel:turismo_dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('painel:turismo_local_novo')).status_code, 403)

    def test_concessao_auditoria_revogacao_e_autoconcessao_bloqueada(self):
        grant = conceder_permissao(
            ator=self.master, beneficiado=self.owner,
            permissao=self.permissions['TURISMO_LOCAL_CADASTRAR'],
            justificativa='Colaborador de turismo',
        )
        self.assertTrue(self.owner.tem_permissao('TURISMO_LOCAL_CADASTRAR'))
        self.assertTrue(AuditoriaPermissao.objects.filter(acao='CONCEDER').exists())
        revogar_permissao(
            ator=self.master, concessao=grant,
            justificativa='Fim da colaboração',
        )
        self.assertFalse(self.owner.tem_permissao('TURISMO_LOCAL_CADASTRAR'))
        self.assertTrue(AuditoriaPermissao.objects.filter(acao='REVOGAR').exists())
        with self.assertRaises(PermissionDenied):
            conceder_permissao(
                ator=self.master, beneficiado=self.master,
                permissao=self.permissions['TURISMO_LOCAL_CADASTRAR'],
                justificativa='Não permitido',
            )

    def test_edicao_propria_e_global_filtradas_no_backend(self):
        own = self.local()
        third_party = self.local(owner=self.other, nome='Museu', slug='museu')
        self.grant(self.owner, 'TURISMO_LOCAL_EDITAR_PROPRIOS')
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('painel:turismo_local_editar', args=[own.uuid])).status_code, 200)
        self.assertEqual(self.client.get(reverse('painel:turismo_local_editar', args=[third_party.uuid])).status_code, 404)
        self.grant(self.owner, 'TURISMO_LOCAL_EDITAR_TODOS')
        self.assertEqual(self.client.get(reverse('painel:turismo_local_editar', args=[third_party.uuid])).status_code, 200)

    def test_publicacao_exige_permissao_e_rascunho_nao_aparece(self):
        local = self.local()
        self.grant(self.owner, 'TURISMO_LOCAL_EDITAR_PROPRIOS')
        self.grant(self.owner, 'TURISMO_LOCAL_ENVIAR_ANALISE')
        self.client.force_login(self.owner)
        self.client.post(reverse('painel:turismo_local_status', args=[local.uuid]), {'status': TurismoStatus.EM_ANALISE})
        local.refresh_from_db()
        self.assertEqual(local.status, TurismoStatus.EM_ANALISE)
        self.client.post(reverse('painel:turismo_local_status', args=[local.uuid]), {'status': TurismoStatus.PUBLICADO})
        local.refresh_from_db()
        self.assertEqual(local.status, TurismoStatus.EM_ANALISE)
        self.assertNotContains(self.client.get(reverse('tourism_public:home')), local.nome)

    def test_moderador_edita_registro_de_terceiro(self):
        local = self.local(owner=self.other)
        permission, _ = Permissao.objects.get_or_create(
            codigo='TURISMO_LOCAL_MODERAR',
            defaults={'modulo': 'Turismo', 'grupo': 'Local', 'nome': 'Moderar locais'},
        )
        ConcessaoPermissao.objects.create(
            usuario=self.owner, permissao=permission,
            concedida_por=self.master, justificativa='Moderação de teste',
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse('painel:turismo_local_editar', args=[local.uuid])).status_code,
            200,
        )

    def test_privacidade_guia_e_local_publicos(self):
        self.owner.cpf = '52998224725'
        self.owner.save(update_fields=['cpf'])
        local = self.local(
            status=TurismoStatus.PUBLICADO,
            visibilidade_localizacao=LocalizacaoVisibilidade.PRIVADA,
            latitude=-22.123456, longitude=-48.123456,
            bairro='Bairro confidencial', cidade='Cidade confidencial',
        )
        guia = GuiaTuristico.objects.create(
            tipo='PF', usuario=self.owner, slug='guia-seguro',
            nome_profissional='Guia Seguro', apresentacao='Apresentação',
            verificado=True, status=TurismoStatus.PUBLICADO,
            usuario_criador=self.owner, usuario_atualizador=self.owner,
        )
        response = self.client.get(reverse('tourism_public:local', args=[local.slug]))
        self.assertNotContains(response, '-22.123456')
        self.assertNotContains(response, '-48.123456')
        self.assertNotContains(response, 'Bairro confidencial')
        self.assertNotContains(response, 'Cidade confidencial')
        response = self.client.get(reverse('tourism_public:guia', args=[guia.slug]))
        self.assertNotContains(response, '52998224725')

    def test_youtube_rejeita_url_e_iframe_arbitrarios(self):
        self.assertEqual(youtube_id('https://youtu.be/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        for value in ('<iframe src="x"></iframe>', 'https://example.com/video'):
            with self.assertRaises(ValidationError):
                youtube_id(value)


@override_settings(
    WEATHER_API_URL='https://weather.test/current',
    WEATHER_API_KEY='segredo-nao-renderizar',
    WEATHER_CITY='Botucatu',
    WEATHER_LATITUDE='-22.8',
    WEATHER_LONGITUDE='-48.4',
    WEATHER_CACHE_SECONDS=1200,
)
class WeatherAndManagementTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_weather_cache_e_falha_segura(self):
        from apps.core.services import weather
        with patch.object(weather, '_fetch', return_value={
            'disponivel': True, 'cidade': 'Botucatu', 'temperatura': 24,
            'condicao': 'Nublado', 'icone': 'cloudy',
            'atualizado_em': None, 'desatualizado': False,
        }) as fetch:
            self.assertEqual(weather.clima_atual()['temperatura'], 24)
            self.assertEqual(weather.clima_atual()['temperatura'], 24)
            fetch.assert_called_once()
        cache.clear()
        with patch.object(weather, '_fetch', side_effect=TimeoutError):
            self.assertFalse(weather.clima_atual()['disponivel'])

    @patch('apps.core.context_processors.weather.clima_atual')
    def test_topbar_renderiza_temperatura_sem_chave(self, weather_mock):
        weather_mock.return_value = {
            'disponivel': True, 'cidade': 'Botucatu', 'temperatura': 24,
            'condicao': 'Nublado', 'desatualizado': False,
        }
        response = self.client.get(reverse('home'))
        self.assertContains(response, '24°')
        self.assertContains(response, 'Botucatu')
        self.assertNotContains(response, 'segredo-nao-renderizar')
        self.assertNotContains(response, 'weather-card')

    @patch('apps.core.context_processors.weather.clima_atual', return_value={'disponivel': False})
    def test_gestao_tem_retorno_ao_site(self, _weather_mock):
        master = Usuario.objects.create_superuser('gestao-tourism', 'gestao-tourism@example.com', 'x')
        self.client.force_login(master)
        response = self.client.get(reverse('gestao:dashboard'))
        self.assertContains(response, reverse('home'))
        self.assertContains(response, 'Retornar ao site')
        self.assertContains(response, 'gestao-return-site__mobile')


class TourismPanelFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.master = Usuario.objects.create_superuser(
            'master-panel-tourism', 'master-panel-tourism@example.com', 'x',
        )
        self.client.force_login(self.master)

    def test_dashboard_listas_e_formularios_principais_renderizam(self):
        routes = [
            'painel:turismo_dashboard', 'painel:turismo_local_novo',
            'painel:turismo_guia_novo', 'painel:turismo_empresa_nova',
            'painel:turismo_video_novo', 'painel:turismo_playlist_nova',
            'painel:turismo_roteiro_novo', 'painel:turismo_experiencia_nova',
        ]
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        for entity in ('locais', 'guias', 'empresas', 'videos', 'playlists', 'roteiros', 'experiencias'):
            with self.subTest(entity=entity):
                response = self.client.get(reverse('painel:turismo_entidade_lista', args=[entity]))
                self.assertEqual(response.status_code, 200)

    def test_home_exibe_apenas_conteudo_publicado_dos_novos_grupos(self):
        common = {'usuario_criador': self.master, 'usuario_atualizador': self.master}
        publicado = RoteiroTuristico.objects.create(
            titulo='Roteiro publicado', slug='roteiro-publicado', resumo='Resumo',
            descricao='Descrição', status=TurismoStatus.PUBLICADO, **common,
        )
        RoteiroTuristico.objects.create(
            titulo='Roteiro privado', slug='roteiro-privado', resumo='Resumo',
            descricao='Descrição', status=TurismoStatus.RASCUNHO, **common,
        )
        ExperienciaTuristica.objects.create(
            titulo='Experiência publicada', slug='experiencia-publicada', resumo='Resumo',
            descricao='Descrição', status=TurismoStatus.PUBLICADO, **common,
        )
        response = self.client.get(reverse('home'))
        self.assertContains(response, publicado.titulo)
        self.assertContains(response, 'Experiência publicada')
        self.assertNotContains(response, 'Roteiro privado')

    def test_crud_generico_preserva_autoria_e_isolamento(self):
        roteiro = RoteiroTuristico.objects.create(
            titulo='Meu roteiro', slug='meu-roteiro', resumo='Resumo',
            descricao='Descrição', usuario_criador=self.master,
            usuario_atualizador=self.master,
        )
        detail = reverse('painel:turismo_entidade_detalhe', args=['roteiros', roteiro.uuid])
        edit = reverse('painel:turismo_entidade_editar', args=['roteiros', roteiro.uuid])
        self.assertEqual(self.client.get(detail).status_code, 200)
        response = self.client.post(edit, {
            'titulo': 'Roteiro atualizado', 'slug': 'meu-roteiro',
            'resumo': 'Resumo', 'descricao': 'Descrição',
        })
        self.assertRedirects(response, detail)
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.titulo, 'Roteiro atualizado')
        self.assertEqual(roteiro.usuario_criador, self.master)


class LocalWizardTests(TestCase):
    def setUp(self):
        cache.clear()
        self.master = Usuario.objects.create_superuser('master-wizard', 'master-wizard@example.com', 'x')
        self.owner = Usuario.objects.create_user('owner-wizard', 'owner-wizard@example.com', 'x')

    def grant(self, user, code):
        permission, _ = Permissao.objects.get_or_create(
            codigo=code, defaults={'modulo': 'Turismo', 'grupo': 'Wizard', 'nome': code},
        )
        return ConcessaoPermissao.objects.create(
            usuario=user, permissao=permission,
            concedida_por=self.master, justificativa='Teste automatizado',
        )

    def local(self, **kwargs):
        categoria, _ = CategoriaTurismo.objects.get_or_create(
            slug='natureza-wizard', defaults={'nome': 'Natureza'},
        )
        return LocalTuristico.objects.create(
            nome=kwargs.pop('nome', 'Local wizard'), slug=kwargs.pop('slug', 'local-wizard'),
            categoria=categoria, descricao_curta='Descrição curta',
            descricao_completa='Descrição pública', usuario_criador=self.owner,
            usuario_atualizador=self.owner, **kwargs,
        )
    def image_file(self, name='local.jpg'):
        stream = BytesIO()
        Image.new('RGB', (1000, 600), '#ffd230').save(stream, 'JPEG')
        return SimpleUploadedFile(name, stream.getvalue(), content_type='image/jpeg')

    def grant_wizard(self):
        for code in (
            'TURISMO_LOCAL_CADASTRAR', 'TURISMO_LOCAL_EDITAR_PROPRIOS',
            'TURISMO_LOCAL_ENVIAR_ANALISE', 'TURISMO_FOTO_CADASTRAR',
            'TURISMO_FOTO_EDITAR_PROPRIAS', 'TURISMO_FOTO_EXCLUIR_PROPRIAS',
            'TURISMO_VIDEO_CADASTRAR', 'TURISMO_VIDEO_EXCLUIR_PROPRIOS',
            'TURISMO_PLAYLIST_CADASTRAR', 'TURISMO_PLAYLIST_EDITAR_PROPRIAS',
        ):
            permission, _ = Permissao.objects.get_or_create(
                codigo=code, defaults={'modulo': 'Turismo', 'grupo': 'Wizard', 'nome': code},
            )
            ConcessaoPermissao.objects.get_or_create(
                usuario=self.owner, permissao=permission,
                defaults={'concedida_por': self.master, 'justificativa': 'Teste do cadastro'},
            )

    def test_cria_rascunho_salva_etapas_e_nao_regride(self):
        self.grant_wizard()
        self.client.force_login(self.owner)
        response = self.client.post(reverse('painel:turismo_local_novo'), {
            'nome': 'Parque em etapas', 'slug': 'parque-em-etapas',
            'descricao_curta': 'Descrição curta',
            'descricao_completa': 'Descrição completa', 'historia': '',
            'situacao_local': 'ABERTO', 'acao': 'continuar',
            'usuario_criador': self.master.pk,
        })
        local = LocalTuristico.objects.get(slug='parque-em-etapas')
        self.assertEqual(local.status, TurismoStatus.RASCUNHO)
        self.assertEqual(local.usuario_criador, self.owner)
        self.assertRedirects(response, reverse('painel:turismo_local_etapa', args=[local.uuid, 2]))
        categoria = CategoriaTurismo.objects.create(nome='Parque', slug='parque-wizard')
        self.client.post(reverse('painel:turismo_local_etapa', args=[local.uuid, 2]), {
            'categoria': categoria.pk, 'acao': 'continuar',
        })
        local.refresh_from_db()
        self.assertEqual(local.etapa_atual, 3)
        self.client.post(reverse('painel:turismo_local_etapa', args=[local.uuid, 1]), {
            'nome': local.nome, 'slug': local.slug, 'descricao_curta': local.descricao_curta,
            'descricao_completa': local.descricao_completa, 'historia': '',
            'situacao_local': local.situacao_local, 'acao': 'salvar',
        })
        local.refresh_from_db()
        self.assertEqual(local.etapa_atual, 3)
        local.etapa_atual = 10
        local.save(update_fields=['etapa_atual'])
        for etapa in range(1, 11):
            with self.subTest(etapa=etapa):
                response = self.client.get(reverse('painel:turismo_local_etapa', args=[local.uuid, etapa]))
                self.assertEqual(response.status_code, 200)

    def test_imagem_principal_processada_e_home_a_utiliza(self):
        local = self.local()
        local.cidade, local.estado = 'Botucatu', 'SP'
        local.imagem_texto_alternativo = 'Vista do parque'
        local.imagem_principal = self.image_file()
        local.status = TurismoStatus.PUBLICADO
        local.save()
        from .services import processar_imagem_principal
        processar_imagem_principal(local)
        local.refresh_from_db()
        self.assertTrue(local.imagem_principal_webp)
        self.assertTrue(local.imagem_thumbnail)
        cache.clear()
        response = self.client.get(reverse('home'))
        self.assertContains(response, local.imagem_thumbnail.url)

    def test_publicacao_sem_imagem_principal_bloqueada(self):
        local = self.local(status=TurismoStatus.EM_ANALISE)
        self.grant(self.owner, 'TURISMO_LOCAL_PUBLICAR')
        with self.assertRaises(ValidationError):
            from apps.tourism.services import alterar_status
            alterar_status(local, self.owner, TurismoStatus.PUBLICADO)

    def test_galeria_multipla_e_exclusao_logica(self):
        self.grant_wizard()
        local = self.local()
        local.etapa_atual = 10
        local.save(update_fields=['etapa_atual'])
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('painel:turismo_local_etapa', args=[local.uuid, 6]),
            {
                'item_tipo': 'foto', 'texto_alternativo': 'Vista do local',
                'credito': 'Equipe BOTUKA',
                'imagens': [self.image_file('vista-1.jpg'), self.image_file('vista-2.jpg')],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(local.fotos.filter(ativo=True).count(), 2)
        foto = local.fotos.first()
        self.client.post(reverse('painel:turismo_local_imagem_remover', args=[local.uuid, foto.uuid]))
        foto.refresh_from_db()
        self.assertFalse(foto.ativo)

    def test_contato_privado_e_midia_nao_publicada_nao_vazam(self):
        local = self.local(status=TurismoStatus.PUBLICADO)
        ContatoTurismo.objects.create(
            local=local, tipo='TELEFONE', valor='(14) 99999-0000',
            publico=False, status=TurismoStatus.PUBLICADO,
            usuario_criador=self.owner, usuario_atualizador=self.owner,
        )
        RedeSocialTurismo.objects.create(
            local=local, tipo='INSTAGRAM', url='https://instagram.com/botuka',
            status=TurismoStatus.RASCUNHO,
            usuario_criador=self.owner, usuario_atualizador=self.owner,
        )
        response = self.client.get(reverse('tourism_public:local', args=[local.slug]))
        self.assertNotContains(response, '(14) 99999-0000')
        self.assertNotContains(response, 'instagram.com/botuka')

    def test_coordenadas_validas_e_limites_invalidos(self):
        local = self.local()
        valid = LocalLocalizacaoForm({
            'cep': '18600-000', 'logradouro': 'Rua Teste', 'numero': '10',
            'complemento': '', 'bairro': 'Centro', 'cidade': 'Botucatu',
            'estado': 'SP', 'ponto_referencia': '', 'latitude': '-22.885800',
            'longitude': '-48.445000', 'precisao': '',
            'visibilidade_localizacao': LocalizacaoVisibilidade.PUBLICA,
        }, instance=local)
        self.assertTrue(valid.is_valid(), valid.errors)
        for field, value in (('latitude', '500'), ('longitude', '-200')):
            data = valid.data.copy()
            data[field] = value
            form = LocalLocalizacaoForm(data, instance=local)
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)

    def test_informacoes_fechadas_catalogos_e_preco_obrigatorio(self):
        local = self.local()
        estrutura = EstruturaTurismo.objects.create(nome='Banheiro teste', slug='banheiro-teste')
        servico = ServicoTurismo.objects.create(nome='Visita teste', slug='visita-teste')
        data = {
            'horario': '', 'dias_funcionamento': '', 'gratuito': 'false',
            'valor_inteiro': '', 'valor_meia': '', 'valor_infantil': '',
            'valor_informativo': '', 'link_compra': '',
            'agendamento_necessario': 'false', 'estruturas': [estrutura.pk],
            'servicos_disponiveis': [servico.pk], 'recomendacoes': '',
            'regras_local': '', 'melhor_periodo': '', 'seguranca': '',
            'duracao_media_visita': '',
        }
        invalid = LocalInformacoesForm(data, instance=local)
        self.assertFalse(invalid.is_valid())
        self.assertIn('valor_inteiro', invalid.errors)
        data['valor_inteiro'] = '25.00'
        valid = LocalInformacoesForm(data, instance=local)
        self.assertTrue(valid.is_valid(), valid.errors)
        saved = valid.save()
        self.assertIn(estrutura, saved.estruturas.all())
        self.assertIn(servico, saved.servicos_disponiveis.all())

    def test_contato_publico_booleano_e_protocolos_validados(self):
        valid = ContatoTurismoForm({
            'tipo': 'WHATSAPP', 'valor': '(14) 99999-0000',
            'nome_exibicao': 'Reservas', 'publico': 'false',
            'principal': 'true', 'ordem': 1,
        })
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertFalse(valid.cleaned_data['publico'])
        invalid = ContatoTurismoForm({
            'tipo': 'SITE', 'valor': 'javascript:alert(1)',
            'nome_exibicao': '', 'publico': 'true', 'principal': 'false', 'ordem': 0,
        })
        self.assertFalse(invalid.is_valid())

    def test_form_invalido_nao_avanca_etapa(self):
        self.grant_wizard()
        local = self.local()
        local.etapa_atual = 3
        local.save(update_fields=['etapa_atual'])
        self.client.force_login(self.owner)
        response = self.client.post(reverse('painel:turismo_local_etapa', args=[local.uuid, 3]), {
            'cidade': 'Botucatu', 'estado': 'SP', 'latitude': '500',
            'longitude': '-48', 'visibilidade_localizacao': 'PUBLICA',
            'acao': 'continuar',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Corrija os campos destacados')
        local.refresh_from_db()
        self.assertEqual(local.etapa_atual, 3)

    def test_destaque_home_e_guias_protegidos_por_queryset(self):
        local = self.local()
        form = LocalTuristicoForm(
            {'nome': local.nome, 'slug': local.slug, 'destaque_home': 'true'},
            instance=local, usuario=self.owner,
        )
        self.assertNotIn('destaque_home', form.fields)
        guia_terceiro = GuiaTuristico.objects.create(
            tipo='PF', usuario=self.master, slug='guia-terceiro-wizard',
            nome_profissional='Guia terceiro', apresentacao='Apresentação',
            verificado=True, status=TurismoStatus.PUBLICADO,
            usuario_criador=self.master, usuario_atualizador=self.master,
        )
        relation_form = LocalRelacoesForm(instance=local, usuario=self.owner)
        self.assertNotIn(guia_terceiro, relation_form.fields['guias_relacionados'].queryset)

    def test_interface_localizacao_solicita_geolocalizacao_somente_por_acao(self):
        self.grant_wizard()
        local = self.local()
        local.etapa_atual = 3
        local.save(update_fields=['etapa_atual'])
        self.client.force_login(self.owner)
        response = self.client.get(reverse('painel:turismo_local_etapa', args=[local.uuid, 3]))
        self.assertContains(response, 'Usar minha localização atual')
        script = (Path(__file__).resolve().parents[2] / 'static' / 'painel' / 'js' / 'turismo-local.js').read_text(encoding='utf-8')
        self.assertIn('locateButton.addEventListener("click"', script)
        self.assertIn('navigator.geolocation.getCurrentPosition', script)
