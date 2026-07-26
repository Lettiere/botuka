import uuid

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class YuBotukaDataMigrationTests(TransactionTestCase):
    migrate_from = ('media', '0002_alter_canal_capa_alter_canal_logotipo_and_more')
    migrate_to = ('media', '0004_migrar_episodios_e_permissoes_yubotuka')

    @property
    def app(self):
        return 'media'

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        sufixo = uuid.uuid4().hex[:8]
        self.slug = f'titulo-do-video-legado-{sufixo}'
        self.canal_slug = f'canal-legado-{sufixo}'
        self.programa_slug = f'programa-legado-{sufixo}'
        self.categoria_nome = f'Esporte legado {sufixo}'
        Canal = old_apps.get_model('media', 'Canal')
        Programa = old_apps.get_model('media', 'Programa')
        Episodio = old_apps.get_model('media', 'Episodio')
        canal = Canal.objects.create(nome='Canal legado', slug=self.canal_slug)
        programa = Programa.objects.create(
            canal=canal, nome='Programa legado', slug=self.programa_slug,
            categoria=self.categoria_nome,
        )
        Episodio.objects.create(
            programa=programa, titulo='Título do vídeo legado',
            slug=self.slug, descricao='Descrição preservada',
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            video_id='dQw4w9WgXcQ', thumbnail='https://example.com/thumb.jpg',
            status='PUBLICADO',
        )
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        from apps.media.models import (
            Canal,
            CategoriaYuBotuka,
            Episodio,
            HomologacaoVideoMigrado,
            Programa,
            Video,
        )
        HomologacaoVideoMigrado.objects.filter(video__slug=self.slug).delete()
        Episodio.all_objects.filter(slug=self.slug).delete()
        Video.all_objects.filter(slug=self.slug).delete()
        Programa.all_objects.filter(slug=self.programa_slug).delete()
        Canal.all_objects.filter(slug=self.canal_slug).delete()
        CategoriaYuBotuka.all_objects.filter(nome=self.categoria_nome).delete()
        super().tearDown()

    def _fixture_teardown(self):
        # O projeto possui tabelas through customizadas que impedem o TRUNCATE
        # global do PostgreSQL. Este teste restaura o schema no tearDown e usa
        # apenas registros efêmeros do app media.
        pass

    def test_preserva_episodio_slug_url_e_relaciona_video(self):
        Episodio = self.apps.get_model('media', 'Episodio')
        Video = self.apps.get_model('media', 'Video')
        episodio = Episodio.objects.get(slug=self.slug)
        video = Video.objects.get(pk=episodio.video_editorial_id)
        self.assertEqual(video.slug, self.slug)
        self.assertEqual(video.youtube_url, episodio.youtube_url)
        self.assertEqual(video.video_id, episodio.video_id)
        self.assertEqual(video.thumbnail, episodio.thumbnail)
        self.assertEqual(video.status, 'PUBLICADO')
        self.assertEqual(video.categoria.nome, self.categoria_nome)
