from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from apps.media.models import Canal,Programa,Episodio

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
