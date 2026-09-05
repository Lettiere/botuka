from django.contrib.sitemaps import Sitemap
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.domain import EditorialStatus
from apps.government.models import AcaoPublica, OrgaoPublico
from apps.media.models import Canal, CategoriaYuBotuka, Episodio, Playlist, Programa
from apps.media.selectors import videos_publicos
from apps.news.models import (
    Artigo, CategoriaNoticia, Coluna, Colunista, SerieEditorial, Tag, Tema,
)
from apps.organizations.models import Empresa
from apps.recruitment.models import Vaga
from apps.services.models import Servico
from apps.sports.models import Atleta, Campeonato, Disputa, Equipe, Modalidade
from apps.tourism.models import GuiaTuristico, LocalTuristico, RoteiroTuristico, TurismoStatus
from apps.events.models import Evento
from apps.products.models import Produto


class HttpsSitemap(Sitemap):
    protocol = 'https'


class StaticSitemap(HttpsSitemap):
    routes = ['home', 'publico:empresas', 'publico:servicos', 'events:lista',
              'news_public:home', 'recruitment_public:vagas', 'sports_public:home',
              'media_public:home', 'government_public:home']
    routes.append('media_public:yubotuka_home')

    def items(self): return self.routes
    def location(self, item): return reverse(item)


class EmpresaSitemap(HttpsSitemap):
    def items(self):
        return Empresa.objects.filter(ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA, excluido_em__isnull=True).only('slug', 'atualizado_em')
    def location(self, item): return reverse('publico:empresa', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class ServicoSitemap(HttpsSitemap):
    def items(self):
        return Servico.objects.publicamente_visiveis().filter(Q(empresa__isnull=True) | Q(empresa__ativo=True, empresa__perfil_publico=True, empresa__status=Empresa.Status.ATIVA)).only('slug', 'atualizado_em')
    def location(self, item): return reverse('publico:servico', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class ArtigoSitemap(HttpsSitemap):
    def items(self):
        return Artigo.objects.filter(status=EditorialStatus.PUBLICADO, publicado_em__lte=timezone.now(), ativo=True, excluido_em__isnull=True).only('slug', 'atualizado_em')
    def location(self, item): return reverse('news_public:artigo', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class CategoriaNoticiaSitemap(HttpsSitemap):
    def items(self): return CategoriaNoticia.objects.filter(ativo=True, excluido_em__isnull=True).only('slug', 'atualizado_em')
    def location(self, item): return reverse('news_public:categoria', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class NewsTaxonomySitemap(HttpsSitemap):
    model_route = {
        Tema: 'news_public:tema',
        Tag: 'news_public:tag',
        SerieEditorial: 'news_public:serie',
        Coluna: 'news_public:coluna',
    }

    def items(self):
        itens = []
        for model in self.model_route:
            itens.extend(model.objects.filter(
                ativo=True, excluido_em__isnull=True,
            ).only('slug', 'atualizado_em'))
        return itens

    def location(self, item):
        return reverse(self.model_route[type(item)], args=[item.slug])

    def lastmod(self, item): return item.atualizado_em


class ColunistaSitemap(HttpsSitemap):
    def items(self):
        return Colunista.objects.filter(
            ativo=True, excluido_em__isnull=True,
            autor__ativo=True, autor__excluido_em__isnull=True,
        ).select_related('autor').only(
            'atualizado_em', 'autor__slug',
        )
    def location(self, item): return reverse('news_public:colunista', args=[item.autor.slug])
    def lastmod(self, item): return item.atualizado_em


class VagaSitemap(HttpsSitemap):
    def items(self):
        return Vaga.objects.filter(status=Vaga.Status.PUBLICADA, publicado_em__isnull=False, empresa__ativo=True, empresa__perfil_publico=True).filter(Q(encerramento__isnull=True) | Q(encerramento__gte=timezone.localdate())).only('slug', 'atualizado_em')
    def location(self, item): return reverse('recruitment_public:vaga', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class ProgramaSitemap(HttpsSitemap):
    def items(self): return Programa.objects.filter(ativo=True, excluido_em__isnull=True, canal__ativo=True, canal__excluido_em__isnull=True).only('slug', 'atualizado_em')
    def location(self, item): return reverse('media_public:programa', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class EpisodioSitemap(HttpsSitemap):
    def items(self): return Episodio.objects.filter(ativo=True, excluido_em__isnull=True, status=EditorialStatus.PUBLICADO, publicado_em__lte=timezone.now(), programa__ativo=True, programa__excluido_em__isnull=True, programa__canal__ativo=True, programa__canal__excluido_em__isnull=True).only('slug', 'atualizado_em')
    def location(self, item): return reverse('media_public:episodio', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class VideoYuBotukaSitemap(HttpsSitemap):
    def items(self): return videos_publicos()
    def location(self, item): return reverse('media_public:video', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class CategoriaYuBotukaSitemap(HttpsSitemap):
    def items(self): return CategoriaYuBotuka.objects.filter(ativo=True, excluido_em__isnull=True, videos__in=videos_publicos()).distinct()
    def location(self, item): return reverse('media_public:categoria', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class PlaylistYuBotukaSitemap(HttpsSitemap):
    def items(self): return Playlist.objects.filter(ativo=True, excluido_em__isnull=True, itens__video__in=videos_publicos()).distinct()
    def location(self, item): return reverse('media_public:playlist', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class CanalYuBotukaSitemap(HttpsSitemap):
    def items(self): return Canal.objects.filter(ativo=True, excluido_em__isnull=True, videos_editoriais__in=videos_publicos()).distinct()
    def location(self, item): return reverse('media_public:canal', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class ModalidadeSitemap(HttpsSitemap):
    def items(self): return Modalidade.objects.filter(ativo=True, excluido_em__isnull=True)
    def location(self, item): return reverse('sports_public:modalidade', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class EquipeSitemap(HttpsSitemap):
    def items(self): return Equipe.objects.filter(ativo=True, excluido_em__isnull=True, organizacao__ativo=True, organizacao__verificado=True, organizacao__excluido_em__isnull=True).order_by('pk')
    def location(self, item): return reverse('sports_public:equipe', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class AtletaSitemap(HttpsSitemap):
    def items(self): return Atleta.objects.filter(ativo=True, excluido_em__isnull=True, publico=True, equipe__organizacao__ativo=True, equipe__organizacao__verificado=True, equipe__organizacao__excluido_em__isnull=True).order_by('pk')
    def location(self, item): return reverse('sports_public:atleta', args=[item.uuid])
    def lastmod(self, item): return item.atualizado_em


class CampeonatoSitemap(HttpsSitemap):
    def items(self): return Campeonato.objects.filter(ativo=True, excluido_em__isnull=True, organizacao__ativo=True, organizacao__verificado=True, organizacao__excluido_em__isnull=True, status__in=[Campeonato.Status.INSCRICOES, Campeonato.Status.AGENDADO, Campeonato.Status.EM_ANDAMENTO, Campeonato.Status.FINALIZADO]).order_by('pk')
    def location(self, item): return reverse('sports_public:campeonato', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class DisputaSitemap(HttpsSitemap):
    def items(self): return Disputa.objects.filter(ativo=True, excluido_em__isnull=True, campeonato__ativo=True, campeonato__excluido_em__isnull=True, campeonato__organizacao__ativo=True, campeonato__organizacao__verificado=True, campeonato__organizacao__excluido_em__isnull=True, status__in=['AGENDADA', 'EM_ANDAMENTO', 'ENCERRADA', 'ADIADA', 'WO']).order_by('pk')
    def location(self, item): return reverse('sports_public:jogo', args=[item.uuid])
    def lastmod(self, item): return item.atualizado_em


class OrgaoSitemap(HttpsSitemap):
    def items(self): return OrgaoPublico.objects.filter(ativo=True, verificado=True, excluido_em__isnull=True)
    def location(self, item): return reverse('government_public:orgao', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class AcaoSitemap(HttpsSitemap):
    def items(self): return AcaoPublica.objects.filter(ativo=True, status=EditorialStatus.PUBLICADO, publicado_em__isnull=False, orgao__ativo=True, orgao__verificado=True, orgao__excluido_em__isnull=True, excluido_em__isnull=True).order_by('pk')
    def location(self, item): return reverse('government_public:acao', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class LocalTuristicoSitemap(HttpsSitemap):
    def items(self):
        return LocalTuristico.objects.filter(status=TurismoStatus.PUBLICADO, ativo=True, removido_em__isnull=True).only('slug', 'atualizado_em')
    def location(self, item): return reverse('tourism_public:local', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class GuiaTuristicoSitemap(HttpsSitemap):
    def items(self):
        return GuiaTuristico.objects.filter(status=TurismoStatus.PUBLICADO, verificado=True, ativo=True, removido_em__isnull=True).only('slug', 'atualizado_em')
    def location(self, item): return reverse('tourism_public:guia', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class RoteiroTuristicoSitemap(HttpsSitemap):
    def items(self):
        return RoteiroTuristico.objects.filter(status=TurismoStatus.PUBLICADO, ativo=True, removido_em__isnull=True).only('slug', 'atualizado_em')
    def location(self, item): return reverse('tourism_public:roteiro', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class EventoSitemap(HttpsSitemap):
    def items(self):
        return Evento.objects.filter(
            status=Evento.Status.PUBLICADO, publico=True,
            publicado_em__isnull=False,
        ).only('slug', 'atualizado_em')
    def location(self, item): return reverse('events:detalhe', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


class ProdutoSitemap(HttpsSitemap):
    def items(self):
        return Produto.objects.filter(
            status=Produto.Status.PUBLICADO, publico=True, ativo=True,
            removido_em__isnull=True, publicado_em__isnull=False,
        ).only('slug', 'atualizado_em')
    def location(self, item): return reverse('products:detalhe', args=[item.slug])
    def lastmod(self, item): return item.atualizado_em


SITEMAPS = {
    'static': StaticSitemap,
    'empresas': EmpresaSitemap,
    'servicos': ServicoSitemap,
    'noticias': ArtigoSitemap,
    'categorias-noticias': CategoriaNoticiaSitemap,
    'taxonomias-noticias': NewsTaxonomySitemap,
    'colunistas-noticias': ColunistaSitemap,
    'vagas': VagaSitemap,
    'ytv-programas': ProgramaSitemap,
    'ytv-episodios': EpisodioSitemap,
    'yubotuka-videos': VideoYuBotukaSitemap,
    'yubotuka-categorias': CategoriaYuBotukaSitemap,
    'yubotuka-playlists': PlaylistYuBotukaSitemap,
    'yubotuka-canais': CanalYuBotukaSitemap,
    'esportes-modalidades': ModalidadeSitemap,
    'esportes-equipes': EquipeSitemap,
    'esportes-atletas': AtletaSitemap,
    'esportes-campeonatos': CampeonatoSitemap,
    'esportes-jogos': DisputaSitemap,
    'prefeitura-orgaos': OrgaoSitemap,
    'prefeitura-acoes': AcaoSitemap,
    'turismo-locais': LocalTuristicoSitemap,
    'turismo-guias': GuiaTuristicoSitemap,
    'turismo-roteiros': RoteiroTuristicoSitemap,
    'eventos-publicos': EventoSitemap,
    'produtos-publicos': ProdutoSitemap,
}
