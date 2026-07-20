from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from apps.government.models import AcaoPublica
from apps.sports.models import Campeonato
from apps.core.services.home.adapters.dto import EventoPublicoDTO
from apps.core.services.home.adapters.events import _imagem
from django.urls import reverse


def eventos_lista(request):
    hoje = timezone.localdate()
    termo = request.GET.get("q", "").strip()[:100]
    tipo = request.GET.get("tipo", "").strip()[:30]
    bairro = request.GET.get("bairro", "").strip()[:100]
    categoria = request.GET.get("categoria", "").strip()[:80]
    periodo = request.GET.get("periodo", "").strip()[:20]
    oficiais = AcaoPublica.objects.filter(tipo=AcaoPublica.Tipo.EVENTO, ativo=True, excluido_em__isnull=True, status="PUBLICADO", publicado_em__lte=timezone.now(), orgao__ativo=True, orgao__verificado=True, orgao__excluido_em__isnull=True).filter(Q(conclusao_prevista__isnull=True) | Q(conclusao_prevista__gte=hoje)).select_related("orgao")
    esportivos = Campeonato.objects.filter(ativo=True, excluido_em__isnull=True, status__in=["INSCRICOES", "AGENDADO", "EM_ANDAMENTO"], organizacao__ativo=True, organizacao__verificado=True, organizacao__excluido_em__isnull=True).filter(Q(data_final__isnull=True) | Q(data_final__gte=hoje)).select_related("organizacao", "modalidade")
    if termo:
        oficiais = oficiais.filter(Q(titulo__icontains=termo) | Q(resumo__icontains=termo) | Q(descricao__icontains=termo) | Q(local__icontains=termo) | Q(bairro__icontains=termo) | Q(orgao__nome__icontains=termo))
        esportivos = esportivos.filter(Q(nome__icontains=termo) | Q(descricao__icontains=termo) | Q(localidade__icontains=termo) | Q(organizacao__nome__icontains=termo) | Q(modalidade__nome__icontains=termo))
    if bairro: oficiais = oficiais.filter(bairro__iexact=bairro)
    if categoria == "cultura":
        oficiais = oficiais.filter(Q(titulo__icontains="cultur") | Q(resumo__icontains="cultur") | Q(descricao__icontains="cultur") | Q(titulo__icontains="festival"))
        esportivos = esportivos.none()
    elif categoria:
        esportivos = esportivos.filter(Q(modalidade__slug=categoria) | Q(modalidade__nome__iexact=categoria))
        oficiais = oficiais.none()
    if tipo == "municipal": esportivos = esportivos.none()
    if tipo == "esportivo": oficiais = oficiais.none()
    inicio, fim = None, None
    if periodo == "hoje": inicio = fim = hoje
    elif periodo == "amanha": inicio = fim = hoje + timedelta(days=1)
    elif periodo == "semana": inicio, fim = hoje, hoje + timedelta(days=7)
    elif periodo == "mes": inicio, fim = hoje, hoje + timedelta(days=31)
    if inicio:
        oficiais = oficiais.filter(inicio_previsto__range=(inicio, fim))
        esportivos = esportivos.filter(data_inicial__range=(inicio, fim))
    itens = [EventoPublicoDTO(a.uuid, a.titulo, a.resumo or a.descricao[:220], "Evento municipal", a.inicio_previsto, a.conclusao_prevista, a.local or a.bairro or a.cidade, a.orgao.nome, True, None, _imagem(a.imagem), reverse("government_public:acao", args=[a.slug]), "Prefeitura") for a in oficiais[:100]]
    itens += [EventoPublicoDTO(c.uuid, c.nome, c.descricao[:220], c.modalidade.nome, c.data_inicial, c.data_final, c.localidade, c.organizacao.nome, False, None, _imagem(c.imagem), reverse("sports_public:campeonato", args=[c.slug]), "Esportes") for c in esportivos[:100]]
    ordem = request.GET.get("ordem")
    itens.sort(key=(lambda x: x.titulo.casefold()) if ordem == "az" else (lambda x: (x.inicio is None, x.inicio or hoje)))
    page = Paginator(itens, 12).get_page(request.GET.get("page"))
    return render(request, "publico/eventos/lista.html", {"eventos": page.object_list, "page_obj": page, "total": page.paginator.count})
