from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from uuid import uuid4
from apps.core.models import Perfil, PerfilPermissao, Permissao
from apps.media.models import (
    Canal,
    CategoriaYuBotuka,
    Convidado,
    Episodio,
    MotivoRejeicao,
    Apresentador,
    Patrocinador,
    Playlist,
    PlaylistVideo,
    Programa,
    Temporada,
    Transmissao,
    CanalUsuario,
    HomologacaoVideoMigrado,
    TagYuBotuka,
    Video,
    VideoApresentador,
    VideoConvidado,
    VideoPatrocinador,
    VideoTag,
)
from apps.media.services import (
    agendar_video,
    aprovar_video,
    arquivar_video,
    enviar_para_analise,
    publicar_video,
    reordenar_playlist,
    rejeitar_video,
    restaurar_video,
    agendar_transmissao,
    aprovar_transmissao,
    atribuir_canal,
    cancelar_transmissao,
    encerrar_transmissao,
    enviar_transmissao_analise,
    homologar_video_migrado,
    iniciar_transmissao,
    publicar_transmissao,
)

class MediaTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('produtor',password='x');self.canal=Canal.objects.create(nome='BOTUKA YTv',oficial=True);self.programa=Programa.objects.create(canal=self.canal,nome='BOTUKA Esportes')
    def test_programa_e_episodio_youtube_valido(self):
        e=Episodio.objects.create(programa=self.programa,titulo='Jogo local',youtube_url='https://youtu.be/dQw4w9WgXcQ',status=Episodio.Status.PUBLICADO)
        self.assertEqual(e.video_id,'dQw4w9WgXcQ');self.assertIn('youtube-nocookie.com',e.embed_url);self.assertEqual(self.client.get(reverse('media_public:episodio',args=[e.slug])).status_code,200)
    def test_url_insegura_rejeitada(self):
        with self.assertRaises(ValidationError):Episodio.objects.create(programa=self.programa,titulo='Ruim',youtube_url='javascript:alert(1)')
    def test_nao_publicado_nao_publico(self):
        e=Episodio.objects.create(programa=self.programa,titulo='Pauta')
        self.assertEqual(self.client.get(reverse('media_public:episodio',args=[e.slug])).status_code,404)


class YuBotukaPermissionAndWorkflowTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.autor = self.User.objects.create_user('autor', password='x')
        self.outro = self.User.objects.create_user('outro', password='x')
        self.moderador = self.User.objects.create_user('moderador', password='x')
        self.publicador = self.User.objects.create_user('publicador', password='x')
        self.master = self.User.objects.create_superuser('master', password='x')
        perfil_admin = Perfil.objects.create(nome='ADMINISTRADOR')
        self.admin = self.User.objects.create_user('admin', password='x', perfil=perfil_admin)
        self.canal = Canal.objects.create(nome='Canal YuBotuka')
        self.programa = Programa.objects.create(canal=self.canal, nome='Esporte local')
        self._conceder(self.autor, *[
            'yubotuka.dashboard.visualizar',
            'yubotuka.video.criar',
            'yubotuka.video.editar_proprio',
            'yubotuka.video.enviar_analise',
        ])
        self._conceder(
            self.moderador,
            'yubotuka.dashboard.visualizar',
            'yubotuka.video.aprovar',
            'yubotuka.video.rejeitar',
        )
        self._conceder(self.publicador, 'yubotuka.video.publicar')
        self._conceder(
            self.autor,
            'yubotuka.video.arquivar',
            'yubotuka.video.agendar',
        )

    def _conceder(self, user, *codes):
        perfil, _ = Perfil.objects.get_or_create(nome=f'PERFIL_{user.username.upper()}')
        user.perfis_adicionais.add(perfil)
        for code in codes:
            permissao = Permissao.objects.get(codigo=code)
            PerfilPermissao.objects.get_or_create(perfil=perfil, permissao=permissao)

    def _video(self, autor=None, status=Video.Status.RASCUNHO, titulo='Vôlei amador'):
        return Video.objects.create(
            titulo=titulo,
            youtube_url='https://youtu.be/dQw4w9WgXcQ',
            canal=self.canal,
            programa=self.programa,
            autor=autor or self.autor,
            status=status,
        )

    def test_usuario_sem_permissao_nao_acessa_dashboard(self):
        self.client.force_login(self.outro)
        response = self.client.get(reverse('painel:yubotuka_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_criador_edita_proprio_e_nao_edita_terceiro(self):
        proprio = self._video()
        terceiro = self._video(autor=self.outro, titulo='Vídeo de terceiro')
        self.client.force_login(self.autor)
        self.assertEqual(
            self.client.get(reverse('painel:yubotuka_video_editar', args=[proprio.uuid])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('painel:yubotuka_video_editar', args=[terceiro.uuid])).status_code,
            404,
        )

    def test_envio_para_analise(self):
        video = enviar_para_analise(self._video(), self.autor)
        self.assertEqual(video.status, Video.Status.EM_ANALISE)
        self.assertEqual(video.historico_editorial.count(), 1)

    def test_autor_nao_publica_diretamente(self):
        video = self._video(status=Video.Status.APROVADO)
        with self.assertRaises(PermissionDenied):
            publicar_video(video, self.autor)

    def test_master_publica(self):
        video = publicar_video(self._video(status=Video.Status.APROVADO), self.master)
        self.assertEqual(video.status, Video.Status.PUBLICADO)

    def test_administrador_publica(self):
        video = publicar_video(self._video(status=Video.Status.APROVADO), self.admin)
        self.assertEqual(video.status, Video.Status.PUBLICADO)

    def test_usuario_com_permissao_especifica_publica(self):
        video = publicar_video(self._video(status=Video.Status.APROVADO), self.publicador)
        self.assertEqual(video.status, Video.Status.PUBLICADO)

    def test_rejeicao_exige_motivo(self):
        video = self._video(status=Video.Status.EM_ANALISE)
        with self.assertRaises(ValidationError):
            rejeitar_video(video, self.moderador, None)

    def test_rejeicao_registra_motivo(self):
        motivo = MotivoRejeicao.objects.create(nome='Metadados incompletos')
        video = rejeitar_video(
            self._video(status=Video.Status.EM_ANALISE),
            self.moderador, motivo, 'Informe a descrição completa.',
        )
        self.assertEqual(video.status, Video.Status.REJEITADO)
        self.assertEqual(video.motivo_rejeicao, motivo)

    def test_transicao_invalida_e_bloqueada(self):
        with self.assertRaises(ValidationError):
            aprovar_video(self._video(), self.moderador)

    def test_slug_deriva_do_titulo_e_fica_estavel_publicado(self):
        video = self._video(titulo='Final do Vôlei Amador')
        self.assertEqual(video.slug, 'final-do-volei-amador')
        video.status = Video.Status.PUBLICADO
        video.save()
        slug_publicado = video.slug
        video.titulo = 'Novo título depois da publicação'
        video.save()
        self.assertEqual(video.slug, slug_publicado)

    def test_categoria_e_subcategoria_hierarquicas(self):
        esporte = CategoriaYuBotuka.objects.create(nome=f'Esporte {uuid4().hex[:8]}')
        volei = CategoriaYuBotuka.objects.create(nome='Vôlei', categoria_pai=esporte)
        self.assertTrue(volei.caminho.endswith(' › Vôlei'))

    def test_playlist_hierarquica_e_video_em_varias_playlists(self):
        esporte = CategoriaYuBotuka.objects.create(nome=f'Esporte {uuid4().hex[:8]}')
        volei = CategoriaYuBotuka.objects.create(nome='Vôlei', categoria_pai=esporte)
        geral = Playlist.objects.create(
            nome='Vôlei', canal=self.canal, categoria=volei,
            proprietario=self.autor,
        )
        amador = Playlist.objects.create(
            nome='Amador', canal=self.canal, categoria=volei,
            playlist_pai=geral, proprietario=self.autor,
        )
        video = self._video()
        PlaylistVideo.objects.create(
            playlist=geral, video=video, ordem=1, adicionado_por=self.autor,
        )
        PlaylistVideo.objects.create(
            playlist=amador, video=video, ordem=1, adicionado_por=self.autor,
        )
        self.assertEqual(amador.caminho, 'Vôlei › Amador')
        self.assertEqual(video.itens_playlist.count(), 2)

    def test_dashboard_autorizado_renderiza(self):
        self.client.force_login(self.autor)
        response = self.client.get(reverse('painel:yubotuka_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gestão YoBotuka')

    def test_manipulacao_de_canal_no_post_e_bloqueada(self):
        canal_proprio = Canal.objects.create(nome='Canal próprio', proprietario=self.autor)
        canal_alheio = Canal.objects.create(nome='Canal alheio', proprietario=self.outro)
        self.client.force_login(self.autor)
        response = self.client.post(reverse('painel:yubotuka_video_novo'), {
            'titulo': 'Tentativa de canal',
            'youtube_url': 'https://youtu.be/dQw4w9WgXcQ',
            'canal': canal_alheio.pk,
            'tipo': Video.Tipo.VIDEO,
            'idioma': Video.Idioma.PT_BR,
            'classificacao': Video.Classificacao.LIVRE,
            'formato': Video.Formato.HORIZONTAL,
            'publico': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Video.objects.filter(titulo='Tentativa de canal').exists())
        self.assertNotEqual(canal_proprio.pk, canal_alheio.pk)

    def test_categoria_impede_ciclo(self):
        raiz = CategoriaYuBotuka.objects.create(nome=f'Raiz {uuid4().hex[:8]}')
        filha = CategoriaYuBotuka.objects.create(nome='Filha', categoria_pai=raiz)
        raiz.categoria_pai = filha
        with self.assertRaises(ValidationError):
            raiz.save()

    def test_playlist_impede_ciclo(self):
        raiz = Playlist.objects.create(
            nome=f'Raiz {uuid4().hex[:8]}', canal=self.canal,
            proprietario=self.autor,
        )
        filha = Playlist.objects.create(
            nome='Filha', canal=self.canal, playlist_pai=raiz,
            proprietario=self.autor,
        )
        raiz.playlist_pai = filha
        with self.assertRaises(ValidationError):
            raiz.save()

    def test_reordenacao_exige_todos_os_videos_e_persiste(self):
        self._conceder(self.autor, 'yubotuka.playlist.gerenciar')
        playlist = Playlist.objects.create(
            nome=f'Ordem {uuid4().hex[:8]}', canal=self.canal,
            proprietario=self.autor,
        )
        primeiro = self._video(titulo='Primeiro')
        segundo = self._video(titulo='Segundo')
        PlaylistVideo.objects.create(playlist=playlist, video=primeiro, ordem=1, adicionado_por=self.autor)
        PlaylistVideo.objects.create(playlist=playlist, video=segundo, ordem=2, adicionado_por=self.autor)
        reordenar_playlist(playlist, self.autor, [segundo.pk, primeiro.pk])
        self.assertEqual(
            list(playlist.itens.order_by('ordem').values_list('video_id', flat=True)),
            [segundo.pk, primeiro.pk],
        )
        with self.assertRaises(ValidationError):
            reordenar_playlist(playlist, self.autor, [primeiro.pk])

    def test_tags_e_participantes_relacionam_video(self):
        video = self._video()
        tag = TagYuBotuka.objects.create(nome=f'Esporte {uuid4().hex[:8]}')
        apresentador = Apresentador.objects.create(nome='Apresentador teste')
        convidado = Convidado.objects.create(nome='Convidado teste')
        patrocinador = Patrocinador.objects.create(nome='Patrocinador teste')
        VideoTag.objects.create(video=video, tag=tag)
        VideoApresentador.objects.create(video=video, apresentador=apresentador)
        VideoConvidado.objects.create(video=video, convidado=convidado)
        VideoPatrocinador.objects.create(video=video, patrocinador=patrocinador)
        self.assertEqual(video.videos_tags.count(), 1)
        self.assertEqual(video.videos_apresentadores.count(), 1)
        self.assertEqual(video.videos_convidados.count(), 1)
        self.assertEqual(video.videos_patrocinadores.count(), 1)

    def test_agendamento_exige_data_futura(self):
        video = self._video(status=Video.Status.APROVADO)
        with self.assertRaises(ValidationError):
            agendar_video(video, self.autor, timezone.now())
        video = agendar_video(
            video, self.autor, timezone.now() + timezone.timedelta(days=1),
        )
        self.assertEqual(video.status, Video.Status.AGENDADO)

    def test_arquivamento_e_restauracao_preservam_registro(self):
        video = self._video(status=Video.Status.PUBLICADO)
        video = arquivar_video(video, self.autor, 'Conteúdo desatualizado')
        self.assertEqual(video.status, Video.Status.ARQUIVADO)
        self.assertTrue(Video.all_objects.filter(pk=video.pk).exists())
        video = restaurar_video(video, self.autor)
        self.assertEqual(video.status, Video.Status.PUBLICADO)

    def test_usuario_nao_arquiva_video_de_terceiro(self):
        video = self._video(autor=self.outro)
        with self.assertRaises(PermissionDenied):
            arquivar_video(video, self.autor, 'Tentativa indevida')

    def test_acoes_criticas_nao_aceitam_get(self):
        video = self._video()
        self.client.force_login(self.autor)
        response = self.client.get(
            reverse('painel:yubotuka_video_enviar_analise', args=[video.uuid]),
        )
        self.assertEqual(response.status_code, 405)

    def test_acao_critica_exige_csrf(self):
        video = self._video()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.autor)
        response = client.post(
            reverse('painel:yubotuka_video_enviar_analise', args=[video.uuid]),
        )
        self.assertEqual(response.status_code, 403)

    def test_video_nao_publicado_e_data_futura_nao_sao_publicos(self):
        rascunho = self._video(titulo='Privado')
        futuro = self._video(status=Video.Status.PUBLICADO, titulo='Futuro')
        futuro.publicado_em = timezone.now() + timezone.timedelta(days=1)
        futuro.save()
        self.assertEqual(
            self.client.get(reverse('media_public:video', args=[rascunho.slug])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse('media_public:video', args=[futuro.slug])).status_code,
            404,
        )

    def test_url_nova_e_url_antiga_renderizam_mesmo_video(self):
        video = self._video(status=Video.Status.PUBLICADO, titulo='Compatibilidade')
        episodio = Episodio.objects.create(
            programa=self.programa, titulo=video.titulo, slug=video.slug,
            youtube_url=video.youtube_url, status=Episodio.Status.PUBLICADO,
            video_editorial=video,
        )
        nova = self.client.get(reverse('media_public:video', args=[video.slug]))
        antiga = self.client.get(reverse('media_public:episodio', args=[episodio.slug]))
        self.assertEqual(nova.status_code, 200)
        self.assertEqual(antiga.status_code, 200)
        self.assertContains(nova, video.titulo)
        self.assertContains(antiga, video.titulo)

    def test_home_publica_yubotuka_renderiza(self):
        self._video(status=Video.Status.PUBLICADO, titulo='Vídeo na home')
        response = self.client.get(reverse('media_public:yubotuka_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'YoBotuka')


class YuBotukaPhaseThreeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.editor = User.objects.create_user('fase3_editor', password='x')
        self.gestor = User.objects.create_user('fase3_gestor', password='x')
        self.intruso = User.objects.create_user('fase3_intruso', password='x')
        self.canal = Canal.objects.create(nome='Canal Fase 3', proprietario=self.editor)
        self.canal_alheio = Canal.objects.create(nome='Canal alheio', proprietario=self.intruso)
        self.programa = Programa.objects.create(canal=self.canal, nome='Programa Fase 3')
        self._conceder(
            self.editor,
            'yubotuka.dashboard.visualizar',
            'yubotuka.programa.gerenciar',
            'yubotuka.temporada.gerenciar',
            'yubotuka.episodio.gerenciar',
            'yubotuka.transmissao.criar',
            'yubotuka.transmissao.editar_propria',
            'yubotuka.transmissao.enviar_analise',
        )
        self._conceder(
            self.gestor,
            'yubotuka.dashboard.visualizar',
            'yubotuka.transmissao.editar_todas',
            'yubotuka.transmissao.aprovar',
            'yubotuka.transmissao.publicar',
            'yubotuka.transmissao.cancelar',
            'yubotuka.canal.atribuir',
            'yubotuka.legado.homologar',
        )

    def _conceder(self, user, *codes):
        perfil = Perfil.objects.create(nome=f'FASE3_{user.username}')
        user.perfis_adicionais.add(perfil)
        for code in codes:
            PerfilPermissao.objects.create(
                perfil=perfil,
                permissao=Permissao.objects.get(codigo=code),
            )

    def _transmissao(self, status=Transmissao.Status.RASCUNHO, prevista=None):
        return Transmissao.objects.create(
            titulo='Live Fase 3',
            canal=self.canal,
            autor=self.editor,
            url_ao_vivo='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            data_prevista=prevista or timezone.now() + timezone.timedelta(hours=1),
            status=status,
        )

    def test_crud_programa_isola_canal_e_bloqueia_post_manipulado(self):
        self.client.force_login(self.editor)
        response = self.client.post(reverse('painel:yubotuka_programa_novo'), {
            'nome': 'Programa permitido', 'canal': self.canal.pk, 'ordem': 1, 'ativo': True,
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse('painel:yubotuka_programa_novo'), {
            'nome': 'Programa indevido', 'canal': self.canal_alheio.pk, 'ordem': 1, 'ativo': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Programa.objects.filter(nome='Programa indevido').exists())

    def test_temporada_valida_duplicidade_datas_e_escopo(self):
        Temporada.objects.create(programa=self.programa, numero=1)
        with self.assertRaises(ValidationError):
            Temporada.objects.create(programa=self.programa, numero=1)
        with self.assertRaises(ValidationError):
            Temporada.objects.create(
                programa=self.programa, numero=2,
                data_inicial=timezone.localdate(),
                data_final=timezone.localdate() - timezone.timedelta(days=1),
            )

    def test_episodio_rejeita_temporada_de_outro_programa(self):
        outro_programa = Programa.objects.create(canal=self.canal, nome='Outro programa')
        temporada = Temporada.objects.create(programa=outro_programa, numero=1)
        with self.assertRaises(ValidationError):
            Episodio.objects.create(
                programa=self.programa, temporada=temporada, titulo='Episódio inválido',
            )

    def test_episodio_associa_video_sem_duplicar(self):
        video = Video.objects.create(
            titulo='Vídeo associado', canal=self.canal, autor=self.editor,
            youtube_url='https://youtu.be/dQw4w9WgXcQ',
        )
        episodio = Episodio.objects.create(
            programa=self.programa, titulo='Episódio associado', video_editorial=video,
        )
        self.assertEqual(episodio.video_editorial_id, video.pk)
        self.assertEqual(Video.objects.filter(pk=video.pk).count(), 1)

    def test_fluxo_completo_da_transmissao(self):
        transmissao = enviar_transmissao_analise(self._transmissao(), self.editor)
        self.assertEqual(transmissao.status, Transmissao.Status.EM_ANALISE)
        transmissao = aprovar_transmissao(transmissao, self.gestor)
        self.assertEqual(transmissao.status, Transmissao.Status.APROVADO)
        transmissao = agendar_transmissao(
            transmissao, self.gestor, timezone.now() + timezone.timedelta(minutes=30),
        )
        transmissao.data_prevista = timezone.now() - timezone.timedelta(minutes=1)
        transmissao.save(update_fields=['data_prevista'])
        transmissao = iniciar_transmissao(transmissao, self.gestor)
        self.assertEqual(transmissao.status, Transmissao.Status.AO_VIVO)
        transmissao = encerrar_transmissao(transmissao, self.gestor)
        transmissao = publicar_transmissao(transmissao, self.gestor)
        self.assertEqual(transmissao.status, Transmissao.Status.PUBLICADA)

    def test_usuario_comum_nao_publica_diretamente(self):
        with self.assertRaises(PermissionDenied):
            aprovar_transmissao(
                self._transmissao(status=Transmissao.Status.EM_ANALISE),
                self.editor,
            )

    def test_cancelamento_e_acoes_criticas_exigem_post(self):
        transmissao = cancelar_transmissao(self._transmissao(), self.gestor)
        self.assertEqual(transmissao.status, Transmissao.Status.CANCELADA)
        self.client.force_login(self.gestor)
        response = self.client.get(
            reverse('painel:yubotuka_transmissao_cancelar', args=[transmissao.uuid]),
        )
        self.assertEqual(response.status_code, 405)

    def test_estado_publico_depende_de_status_e_datas(self):
        futuro = self._transmissao(status=Transmissao.Status.AGENDADA)
        rascunho = self._transmissao(status=Transmissao.Status.RASCUNHO)
        self.assertEqual(
            self.client.get(reverse('media_public:transmissao', args=[futuro.slug])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('media_public:transmissao', args=[rascunho.slug])).status_code,
            404,
        )
        self.assertEqual(self.client.get('/yubotuka/ao-vivo/').status_code, 200)

    def test_atribuicao_de_canal_nao_ocorre_automaticamente(self):
        canal = Canal.objects.create(nome='Canal sem responsável')
        self.assertIsNone(canal.proprietario)
        atribuir_canal(
            canal, self.gestor, self.editor, self.editor, True, False,
            'Responsável confirmado em homologação.',
        )
        canal.refresh_from_db()
        self.assertEqual(canal.proprietario, self.editor)
        self.assertTrue(CanalUsuario.objects.filter(canal=canal, usuario=self.editor).exists())

    def test_homologacao_preserva_slug_e_url_validos(self):
        video = Video.objects.create(
            titulo='Episódio Demo 12', slug='episodio-demo-12',
            youtube_url='https://www.youtube.com/watch?v=98mhMP8ZEV0',
            canal=self.canal,
        )
        episodio = Episodio.objects.create(
            programa=self.programa, titulo='Episódio Demo 12 legado',
            slug='episodio-demo-12-legado', youtube_url='',
            video_editorial=video,
        )
        homologacao = HomologacaoVideoMigrado.objects.create(
            video=video, episodio_legado=episodio,
            divergencias={'youtube_url': {'legado': '', 'video': video.youtube_url}},
        )
        slug, url = video.slug, video.youtube_url
        homologar_video_migrado(
            homologacao, self.gestor, self.editor, self.canal, None,
            observacao='URL nova confirmada.',
        )
        video.refresh_from_db()
        homologacao.refresh_from_db()
        self.assertEqual((video.slug, video.youtube_url), (slug, url))
        self.assertTrue(homologacao.homologado)
