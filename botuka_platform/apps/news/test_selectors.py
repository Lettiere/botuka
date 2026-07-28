from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import (
    Artigo, Autor, CategoriaNoticia, Coluna, Colunista,
    DestaqueEditorial, EditorialStatus, Tema,
)
from .selectors import artigos_publicos, obter_home_noticias


class NewsSelectorTests(TestCase):
    def setUp(self):
        self.agora = timezone.now()
        self.usuario = get_user_model().objects.create_user("selector-news")
        self.autor = Autor.objects.create(
            usuario=self.usuario, nome="Autora Editorial",
        )
        self.cidade = CategoriaNoticia.objects.create(nome="Cidade")
        self.agro = CategoriaNoticia.objects.create(nome="Agro")
        self.universidade = Tema.objects.create(nome="Universidade")

    def artigo(self, titulo, categoria=None, **kwargs):
        defaults = {
            "autor": self.usuario,
            "autor_editorial": self.autor,
            "categoria": categoria or self.cidade,
            "titulo": titulo,
            "conteudo": "Conteúdo",
            "status": EditorialStatus.PUBLICADO,
            "publicado_em": self.agora - timedelta(hours=1),
        }
        defaults.update(kwargs)
        return Artigo.objects.create(**defaults)

    def test_publicos_exclui_estados_datas_e_exclusao_logica(self):
        valido = self.artigo("Publicado")
        self.artigo("Futuro", publicado_em=self.agora + timedelta(days=1))
        self.artigo("Rascunho", status=EditorialStatus.RASCUNHO)
        inativo = self.artigo("Inativo", ativo=False)
        excluido = self.artigo("Excluído")
        excluido.delete()
        ids = set(artigos_publicos(self.agora).values_list("pk", flat=True))
        self.assertEqual(ids, {valido.pk})
        self.assertNotIn(inativo.pk, ids)

    def test_blocos_nao_repetem_artigos(self):
        artigos = [self.artigo(f"Notícia {indice}") for indice in range(12)]
        DestaqueEditorial.objects.create(
            artigo=artigos[0],
            posicao=DestaqueEditorial.Posicao.HOME_PRINCIPAL,
        )
        home = obter_home_noticias(self.agora)
        ids = []
        for chave in ("destaques", "recentes", "agro", "universidade"):
            ids.extend(item.pk for item in home[chave])
        ids.append(home["manchete"].pk)
        self.assertEqual(len(ids), len(set(ids)))

    def test_destaque_futuro_ou_expirado_nao_vira_manchete(self):
        expirado = self.artigo("Expirado")
        futuro = self.artigo("Futuro destaque")
        recente = self.artigo("Manchete válida")
        DestaqueEditorial.objects.create(
            artigo=expirado,
            posicao=DestaqueEditorial.Posicao.HOME_PRINCIPAL,
            fim=self.agora - timedelta(minutes=1),
        )
        DestaqueEditorial.objects.create(
            artigo=futuro,
            posicao=DestaqueEditorial.Posicao.HOME_PRINCIPAL,
            inicio=self.agora + timedelta(minutes=1),
        )
        self.assertEqual(
            obter_home_noticias(self.agora)["manchete"].pk, recente.pk,
        )

    def test_areas_usam_categoria_ou_tema_configurado(self):
        agro = self.artigo("Produção rural", categoria=self.agro)
        universidade = self.artigo("Pesquisa universitária")
        universidade.temas.add(self.universidade)
        geral = self.artigo("Educação geral")
        for indice in range(8):
            self.artigo(f"Notícia geral {indice}")
        home = obter_home_noticias(self.agora)
        self.assertIn(agro, home["agro"])
        self.assertIn(universidade, home["universidade"])
        self.assertNotIn(geral, home["universidade"])

    def test_colunista_inativo_ou_sem_conteudo_nao_aparece(self):
        Coluna.objects.create(autor=self.autor, nome="Cidade em pauta")
        valido = Colunista.objects.create(autor=self.autor, destaque=True)
        outro_usuario = get_user_model().objects.create_user("sem-conteudo")
        outro_autor = Autor.objects.create(
            usuario=outro_usuario, nome="Sem conteúdo",
        )
        Colunista.objects.create(autor=outro_autor)
        nomes = obter_home_noticias(self.agora)["colunistas"]
        self.assertIn(valido, nomes)
        self.assertNotIn(outro_autor.perfil_colunista, nomes)
