from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core.domain_views import crud_views
from apps.core.seo.page_builders import listing_seo, media_seo

from .models import Canal, Episodio, Pauta, Programa, Temporada, Transmissao


def _manager(user):
    return user.tem_permissao("media.gerenciar")


def filtrar_fks_media(user, form):
    if "canal" in form.fields:
        form.fields["canal"].queryset = Canal.objects.all()
    if "programa" in form.fields:
        form.fields["programa"].queryset = Programa.objects.filter(canal__ativo=True, canal__excluido_em__isnull=True)
    if "temporada" in form.fields:
        form.fields["temporada"].queryset = Temporada.objects.filter(programa__ativo=True, programa__excluido_em__isnull=True)
    if "episodio" in form.fields:
        form.fields["episodio"].queryset = Episodio.objects.filter(programa__ativo=True, programa__canal__ativo=True)
    if "oficial" in form.fields and not _manager(user):
        form.fields["oficial"].disabled = True


def validar_estado_episodio(user, anterior, novo, obj):
    allowed = {
        None: {Episodio.Status.PAUTA, Episodio.Status.PRODUCAO},
        Episodio.Status.PAUTA: {Episodio.Status.PAUTA, Episodio.Status.PRODUCAO, Episodio.Status.CANCELADO},
        Episodio.Status.PRODUCAO: {Episodio.Status.PRODUCAO, Episodio.Status.GRAVADO, Episodio.Status.CANCELADO},
        Episodio.Status.GRAVADO: {Episodio.Status.GRAVADO, Episodio.Status.EDITANDO, Episodio.Status.CANCELADO},
        Episodio.Status.EDITANDO: {Episodio.Status.EDITANDO, Episodio.Status.AGENDADO, Episodio.Status.PUBLICADO, Episodio.Status.CANCELADO},
        Episodio.Status.AGENDADO: {Episodio.Status.AGENDADO, Episodio.Status.AO_VIVO, Episodio.Status.PUBLICADO, Episodio.Status.CANCELADO},
        Episodio.Status.AO_VIVO: {Episodio.Status.AO_VIVO, Episodio.Status.PUBLICADO, Episodio.Status.CANCELADO},
        Episodio.Status.PUBLICADO: {Episodio.Status.PUBLICADO, Episodio.Status.CANCELADO},
        Episodio.Status.CANCELADO: {Episodio.Status.CANCELADO},
    }
    if novo not in allowed.get(anterior, set()):
        raise PermissionDenied("Transição de episódio inválida.")
    if novo in {Episodio.Status.AGENDADO, Episodio.Status.AO_VIVO, Episodio.Status.PUBLICADO} and not (user.tem_permissao("media.publicar") or _manager(user)):
        raise PermissionDenied


def _crud(model, fields, transition=None, permissions=None):
    return crud_views(model, "media", fields, filter_form=filtrar_fks_media, permissions=permissions or {}, validate_transition=transition)


canal_lista, canal_novo, canal_editar = _crud(Canal, ["nome", "descricao", "plataforma", "identificador_externo", "url", "logotipo", "capa", "oficial", "ativo"])
programa_lista, programa_novo, programa_editar = _crud(Programa, ["canal", "nome", "descricao", "categoria", "apresentador", "produtor", "imagem", "frequencia", "duracao_media", "ativo"], permissions={"listar": ("media.apresentar",)})
temporada_lista, temporada_novo, temporada_editar = _crud(Temporada, ["programa", "numero", "titulo", "descricao", "data_inicial", "data_final", "ativo"])
episodio_lista, episodio_novo, episodio_editar = _crud(Episodio, ["programa", "temporada", "titulo", "descricao", "numero", "tipo", "youtube_url", "thumbnail", "duracao", "data_gravacao", "data_programada", "status", "destaque", "ativo"], validar_estado_episodio, {"listar": ("media.apresentar",)})
transmissao_lista, transmissao_novo, transmissao_editar = _crud(Transmissao, ["episodio", "disputa", "acao_publica", "data_prevista", "inicio", "fim", "url_ao_vivo", "status", "ativo"], permissions={"listar": ("media.transmitir",), "criar": ("media.transmitir",), "editar": ("media.transmitir",), "publicar": ("media.transmitir",)})
pauta_lista, pauta_novo, pauta_editar = _crud(Pauta, ["titulo", "descricao", "programa", "convidados", "roteiro", "data_prevista", "status", "observacoes", "ativo"])


def _public_episodes():
    return Episodio.objects.filter(status=Episodio.Status.PUBLICADO, publicado_em__isnull=False, publicado_em__lte=timezone.now(), programa__ativo=True, programa__excluido_em__isnull=True, programa__canal__ativo=True, programa__canal__excluido_em__isnull=True).select_related("programa", "programa__canal")


def _visible_episodes():
    return Episodio.objects.filter(status__in=[Episodio.Status.PUBLICADO, Episodio.Status.AO_VIVO], programa__ativo=True, programa__excluido_em__isnull=True, programa__canal__ativo=True, programa__canal__excluido_em__isnull=True).select_related("programa", "programa__canal")


def home(request):
    episodes = _public_episodes().order_by("-destaque", "-publicado_em")
    q = request.GET.get("q", "").strip()[:100]
    categoria = request.GET.get("categoria", "").strip()[:80]
    if q: episodes = episodes.filter(Q(titulo__icontains=q) | Q(descricao__icontains=q) | Q(programa__nome__icontains=q))
    if categoria: episodes = episodes.filter(programa__categoria__iexact=categoria)
    page = Paginator(episodes, 12).get_page(request.GET.get("page"))
    programas = Programa.objects.filter(ativo=True, excluido_em__isnull=True, canal__ativo=True, canal__excluido_em__isnull=True).select_related("canal")
    categorias = programas.exclude(categoria="").values_list("categoria", flat=True).distinct().order_by("categoria")
    seo = listing_seo(request, 'YTv Botuka | Vídeos de Botucatu', 'Programas, entrevistas, vídeos e transmissões locais da YTv Botuka.')
    return render(request, "publico/ytv/home.html", {"programas": programas[:12], "episodios": page.object_list, "page_obj": page, "total": page.paginator.count, "categorias": categorias, "destaque": page.object_list[0] if page.object_list else None, "seo": seo})


def programa(request, slug):
    queryset = Programa.objects.filter(ativo=True, excluido_em__isnull=True, canal__ativo=True, canal__excluido_em__isnull=True).select_related("canal")
    programa_obj = get_object_or_404(queryset, slug=slug)
    episodios = _public_episodes().filter(programa=programa_obj).order_by("-publicado_em")
    page = Paginator(episodios, 12).get_page(request.GET.get("page"))
    return render(request, "publico/ytv/programa.html", {"programa": programa_obj, "episodios": page.object_list, "page_obj": page, "total": page.paginator.count, "seo": media_seo(request, programa_obj)})


def episodio(request, slug):
    episodio_obj = get_object_or_404(_visible_episodes(), slug=slug)
    relacionados = _public_episodes().filter(programa=episodio_obj.programa).exclude(pk=episodio_obj.pk).order_by("-publicado_em")[:4]
    return render(request, "publico/ytv/episodio.html", {"episodio": episodio_obj, "relacionados": relacionados, "seo": media_seo(request, episodio_obj, kind='episodio')})


def ao_vivo(request):
    transmissions = Transmissao.objects.filter(ativo=True, excluido_em__isnull=True, status=Transmissao.Status.AO_VIVO, episodio__ativo=True, episodio__excluido_em__isnull=True, episodio__status=Episodio.Status.AO_VIVO, episodio__video_id__gt="", episodio__programa__ativo=True, episodio__programa__excluido_em__isnull=True, episodio__programa__canal__ativo=True, episodio__programa__canal__excluido_em__isnull=True).select_related("episodio", "episodio__programa").order_by("-inicio")
    recentes = _public_episodes().order_by("-publicado_em")[:4]
    seo = listing_seo(request, 'YTv Botuka ao vivo', 'Transmissões e conteúdos audiovisuais locais da YTv Botuka.')
    return render(request, "publico/ytv/ao_vivo.html", {"transmissoes": transmissions, "recentes": recentes, "seo": seo})
