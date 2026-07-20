from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from apps.core.domain import EditorialStatus
from apps.core.models import Perfil,Permissao,PerfilPermissao
from apps.news.models import CategoriaNoticia,Artigo,ArtigoBloco

class NewsTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('reporter',password='x');p=Perfil.objects.create(nome='NEWS_REPORTER');self.user.perfil=p;self.user.save();perm=Permissao.objects.create(codigo='news.criar',nome='Criar');PerfilPermissao.objects.create(perfil=p,permissao=perm);self.cat=CategoriaNoticia.objects.create(nome='Cidade')
    def test_categoria_criminal_rejeitada(self):
        with self.assertRaises(ValidationError):CategoriaNoticia.objects.create(nome='Noticiário policial')
    def test_artigo_privado_e_publicado(self):
        a=Artigo.objects.create(autor=self.user,categoria=self.cat,titulo='Cidade em pauta',conteudo='Texto seguro')
        self.assertEqual(self.client.get(reverse('news_public:artigo',args=[a.slug])).status_code,404);a.status=EditorialStatus.PUBLICADO;a.save();self.assertEqual(self.client.get(reverse('news_public:artigo',args=[a.slug])).status_code,200)
    def test_bloco_inseguro_rejeitado(self):
        a=Artigo.objects.create(autor=self.user,categoria=self.cat,titulo='Teste',conteudo='Seguro')
        with self.assertRaises(ValidationError):ArtigoBloco.objects.create(artigo=a,tipo=ArtigoBloco.Tipo.TEXTO,conteudo='<script>alert(1)</script>')
    def test_reporter_nao_publica_pelo_painel(self):
        self.client.force_login(self.user);dados={'categoria':self.cat.pk,'titulo':'Sem publicação direta','conteudo':'Texto','status':EditorialStatus.PUBLICADO,'ativo':'on'};r=self.client.post(reverse('painel:news_artigo_novo'),dados);self.assertEqual(r.status_code,200);self.assertFalse(Artigo.objects.filter(titulo='Sem publicação direta').exists())
