from math import ceil
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.forms import modelform_factory
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from apps.accounts.permissions import usuario_tem_permissao
from apps.accounts.authorization import escopo_da_permissao, pode
from apps.accounts.models import AcessoModulo
from apps.core.domain import auditar
from apps.core.seo.page_builders import artigo_seo, listing_seo
from apps.core.services.home.adapters.events import obter_eventos
from apps.core.services.public_urls import build_public_absolute_url

from .models import (
    Artigo, ArtigoBloco, ArtigoFonte, Autor, CategoriaNoticia, Coluna,
    ComentarioArtigo, CurtidaComentario, DenunciaComentario,
    Colunista, DestaqueEditorial, EditorialStatus, EspecialidadeAutor,
    HistoricoEditorial, ImagemPublicacao, LinkRelacionado, MidiaIncorporada,
    SerieEditorial, Tag, Tema,
)
from .services import (
    PERMISSAO_TRANSICAO, TRANSICOES, alterar_status, pode_editar_artigo,
)
from .forms import ArtigoForm, ArtigoVideoFormSet, ComentarioForm
from .selectors import artigos_publicos, obter_home_noticias

NEWS_AUX_MENU = [
    ("autores", "Autores"), ("colunistas", "Colunistas"), ("colunas", "Colunas"),
    ("categorias", "Categorias"), ("temas", "Temas"), ("tags", "Tags"),
    ("especialidades", "Especialidades"), ("series", "Séries editoriais"),
    ("fontes", "Fontes"), ("links", "Links"), ("midias", "Mídias"),
    ("imagens", "Imagens"), ("destaques", "Destaques"),
]


def _links_publicos_artigo(request, links):
    """Normaliza links legados e diferencia navegação interna de externa."""

    canonical_host = urlsplit(settings.PUBLIC_BASE_URL).hostname
    request_host = urlsplit(f"//{request.get_host()}").hostname
    resultado = []
    for link in links:
        try:
            url = build_public_absolute_url(request, link.url)
        except (TypeError, ValueError):
            continue
        host = urlsplit(url).hostname
        externo = bool(host and host not in {canonical_host, request_host})
        resultado.append({
            'titulo': link.titulo,
            'url': url,
            'tipo': link.get_tipo_display(),
            'externo': externo,
            'nofollow': link.nofollow,
        })
    return resultado


def _can(user, *codes):
    return any(
        pode(user, code)
        for code in (*codes, "news.gerenciar")
    )


def _published_articles():
    return artigos_publicos()


def _listing(request, queryset, titulo, descricao, extra=None):
    query = request.GET.get("q", "").strip()[:100]
    if query:
        queryset = queryset.filter(
            Q(titulo__icontains=query)
            | Q(resumo__icontains=query)
            | Q(conteudo__icontains=query)
        )
    page = Paginator(queryset, 12).get_page(request.GET.get("page"))
    contexto = {
        "artigos": page.object_list,
        "page_obj": page,
        "total": page.paginator.count,
        "categorias": CategoriaNoticia.objects.filter(
            ativo=True, excluido_em__isnull=True,
        )[:24],
        "seo": listing_seo(request, titulo, descricao),
    }
    contexto.update(extra or {})
    return render(request, "publico/news/home.html", contexto)


def home(request):
    editorial = obter_home_noticias()
    return _listing(
        request, _published_articles(),
        "Notícias de Botucatu | BOTUKA",
        "Informação local sobre desenvolvimento, ciência, economia, cultura e comunidade.",
        {
            "noticia_manchete": editorial["manchete"],
            "noticias_destaque": editorial["destaques"],
            "noticias_recentes": editorial["recentes"],
            "noticias_agro": editorial["agro"],
            "noticias_universidade": editorial["universidade"],
            "noticias_colunistas": editorial["colunistas"],
            "series_editoriais": SerieEditorial.objects.filter(
                ativo=True, excluido_em__isnull=True,
                artigos__in=_published_articles(),
            ).distinct()[:6],
        },
    )


def legacy_home(request):
    return HttpResponsePermanentRedirect(reverse("news_public:home"))


def categoria(request, slug):
    obj = get_object_or_404(CategoriaNoticia.objects, slug=slug)
    return _listing(
        request, _published_articles().filter(categoria=obj),
        f"{obj.nome} em Botucatu | BOTUKA",
        obj.descricao or f"Conteúdos de {obj.nome} publicados no BOTUKA.",
        {"categoria": obj},
    )


def tema(request, slug):
    obj = get_object_or_404(Tema.objects, slug=slug)
    return _listing(
        request, _published_articles().filter(temas=obj),
        f"{obj.nome} | BOTUKA Notícias", obj.descricao or obj.nome,
        {"tema": obj},
    )


def tag(request, slug):
    obj = get_object_or_404(Tag.objects, slug=slug)
    return _listing(
        request, _published_articles().filter(tags=obj),
        f"{obj.nome} | BOTUKA Notícias", obj.descricao or obj.nome,
        {"tag": obj},
    )


def serie(request, slug):
    obj = get_object_or_404(SerieEditorial.objects, slug=slug)
    return _listing(
        request, _published_articles().filter(serie=obj),
        f"{obj.nome} | BOTUKA Notícias", obj.descricao or obj.nome,
        {"serie": obj},
    )


def coluna(request, slug):
    obj = get_object_or_404(
        Coluna.objects.select_related("autor"), slug=slug,
    )
    return _listing(
        request, _published_articles().filter(coluna=obj),
        f"{obj.nome} | BOTUKA Notícias", obj.descricao or obj.nome,
        {"coluna": obj},
    )


def colunistas(request):
    queryset = (
        Colunista.objects.select_related("autor")
        .prefetch_related("autor__especialidades", "autor__colunas")
    )
    return render(request, "publico/news/colunistas.html", {
        "colunistas": queryset,
        "seo": listing_seo(
            request, "Colunistas | BOTUKA Notícias",
            "Conheça os especialistas e colunistas do BOTUKA.",
        ),
    })


def colunista(request, slug):
    obj = get_object_or_404(
        Colunista.objects.select_related("autor").prefetch_related(
            "autor__especialidades", "autor__colunas",
        ),
        autor__slug=slug,
    )
    return _listing(
        request, _published_articles().filter(autor_editorial=obj.autor),
        f"{obj.autor.nome} | BOTUKA Notícias",
        obj.autor.mini_bio or f"Artigos de {obj.autor.nome}.",
        {"colunista": obj},
    )


def artigo(request, slug):
    queryset = _published_articles().prefetch_related(
        Prefetch("blocos", queryset=ArtigoBloco.objects.all()),
        Prefetch("fontes", queryset=ArtigoFonte.objects.filter(exibir_publicamente=True)),
        Prefetch("links_relacionados", queryset=LinkRelacionado.objects.all()),
        Prefetch("midias", queryset=MidiaIncorporada.objects.select_related("episodio")),
        Prefetch("imagens", queryset=ImagemPublicacao.objects.all()),
        "tags", "temas",
    )
    obj = get_object_or_404(queryset, slug=slug)
    relacionados = list(
        _published_articles().filter(categoria=obj.categoria).exclude(pk=obj.pk)[:4]
    )
    recentes = list(_published_articles().exclude(pk=obj.pk)[:5])
    destaques = list(
        _published_articles().filter(destaque=True).exclude(pk=obj.pk)[:5]
    ) or recentes[:5]
    agora = timezone.now()
    categorias = CategoriaNoticia.objects.annotate(
        total_publicado=Count(
            "artigos",
            filter=Q(
                artigos__status=EditorialStatus.PUBLICADO,
                artigos__publicado_em__lte=agora,
                artigos__ativo=True,
                artigos__excluido_em__isnull=True,
            ),
        ),
    ).filter(total_publicado__gt=0)[:10]
    evento_destaque, eventos_recentes = obter_eventos()
    eventos = list(evento_destaque) + list(eventos_recentes[:3])
    total_palavras = len(obj.conteudo.split()) + sum(
        len(bloco.conteudo.split()) for bloco in obj.blocos.all()
    )
    conteudo_visivel = bool(
        strip_tags(obj.conteudo or '').strip()
        or any(strip_tags(bloco.conteudo or '').strip() for bloco in obj.blocos.all())
        or obj.midias.all()
        or obj.imagens.all()
    )
    comentarios_qs = (
        ComentarioArtigo.objects.filter(
            artigo=obj, comentario_raiz__isnull=True,
            status=ComentarioArtigo.Status.PUBLICADO,
        )
        .select_related("usuario")
        .prefetch_related(Prefetch(
            "respostas",
            queryset=ComentarioArtigo.objects.filter(
                status=ComentarioArtigo.Status.PUBLICADO,
            ).select_related("usuario", "usuario_mencionado").annotate(total_curtidas=Count("curtidas")).order_by("criado_em"),
        ))
        .annotate(total_curtidas=Count("curtidas"))
        .order_by("-criado_em")
    )
    pagina_comentarios = Paginator(comentarios_qs, 10).get_page(request.GET.get("comentarios"))
    return render(request, "publico/news/artigo.html", {
        "artigo": obj,
        "share_object": obj,
        "share_type": "noticia",
        "relacionados": relacionados,
        "recentes": recentes,
        "destaques": destaques,
        "categorias_sidebar": categorias,
        "eventos_sidebar": eventos[:3],
        "tempo_leitura": max(1, ceil(total_palavras / 200)),
        "conteudo_visivel": conteudo_visivel,
        "links_publicos": _links_publicos_artigo(
            request, obj.links_relacionados.all()
        ),
        "pagina_comentarios": pagina_comentarios,
        "comentario_form": ComentarioForm(),
        "seo": artigo_seo(request, obj),
    })


def _artigo_publicado(slug):
    return get_object_or_404(_published_articles(), slug=slug)


def _validar_novo_comentario(request, artigo_obj):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if not request.user.is_active:
        raise PermissionDenied
    if not artigo_obj.comentarios_permitidos or artigo_obj.comentarios_encerrados:
        raise PermissionDenied("Os comentários estão encerrados.")
    key = f"news-comment-rate:{request.user.pk}"
    total = cache.get(key, 0)
    if total >= 5:
        raise PermissionDenied("Aguarde antes de publicar outro comentário.")
    cache.set(key, total + 1, 60)


@login_required
@require_POST
def comentario_novo(request, slug):
    artigo_obj = _artigo_publicado(slug)
    _validar_novo_comentario(request, artigo_obj)
    form = ComentarioForm(request.POST)
    if form.is_valid():
        comentario = form.save(commit=False)
        comentario.artigo = artigo_obj
        comentario.usuario = request.user
        comentario.status = (
            ComentarioArtigo.Status.PENDENTE
            if artigo_obj.comentarios_moderados
            else ComentarioArtigo.Status.PUBLICADO
        )
        comentario.save()
        auditar(request, "COMENTAR_NOTICIA", comentario)
        messages.success(request, "Comentário enviado para moderação." if artigo_obj.comentarios_moderados else "Comentário publicado.")
    else:
        messages.error(request, "; ".join(
            str(error) for errors in form.errors.values() for error in errors
        ))
    return redirect(f"{artigo_obj.get_absolute_url()}#comentarios")


@login_required
@require_POST
def comentario_responder(request, uuid):
    alvo = get_object_or_404(ComentarioArtigo.objects.select_related("artigo", "usuario", "comentario_raiz"), uuid=uuid)
    _validar_novo_comentario(request, alvo.artigo)
    form = ComentarioForm(request.POST)
    if form.is_valid():
        resposta = form.save(commit=False)
        resposta.artigo = alvo.artigo
        resposta.usuario = request.user
        resposta.comentario_raiz = alvo.comentario_raiz or alvo
        resposta.respondendo_a = alvo
        resposta.usuario_mencionado = alvo.usuario if alvo.usuario_id != request.user.pk else None
        resposta.status = ComentarioArtigo.Status.PENDENTE if alvo.artigo.comentarios_moderados else ComentarioArtigo.Status.PUBLICADO
        resposta.save()
        auditar(request, "RESPONDER_COMENTARIO", resposta)
        messages.success(request, "Resposta publicada." if resposta.status == ComentarioArtigo.Status.PUBLICADO else "Resposta enviada para moderação.")
    return redirect(f"{alvo.artigo.get_absolute_url()}#comentarios")


@login_required
@require_POST
def comentario_editar(request, uuid):
    comentario = get_object_or_404(ComentarioArtigo.objects.select_related("artigo"), uuid=uuid)
    if comentario.usuario_id != request.user.pk:
        raise PermissionDenied
    form = ComentarioForm(request.POST, instance=comentario)
    if form.is_valid():
        comentario = form.save(commit=False)
        comentario.editado_em = timezone.now()
        comentario.save()
        auditar(request, "EDITAR_COMENTARIO", comentario)
    return redirect(f"{comentario.artigo.get_absolute_url()}#comentarios")


@login_required
@require_POST
def comentario_excluir(request, uuid):
    comentario = get_object_or_404(ComentarioArtigo.objects.select_related("artigo"), uuid=uuid)
    if comentario.usuario_id != request.user.pk and not _can(request.user, "news.moderar_comentarios"):
        raise PermissionDenied
    comentario.delete()
    auditar(request, "EXCLUIR_COMENTARIO", comentario)
    return redirect(f"{comentario.artigo.get_absolute_url()}#comentarios")


@login_required
@require_POST
def comentario_curtir(request, uuid):
    comentario = get_object_or_404(ComentarioArtigo.objects, uuid=uuid, status=ComentarioArtigo.Status.PUBLICADO)
    curtida, criada = CurtidaComentario.objects.get_or_create(comentario=comentario, usuario=request.user)
    if not criada:
        curtida.delete()
    return redirect(f"{comentario.artigo.get_absolute_url()}#comentarios")


@login_required
@require_POST
def comentario_denunciar(request, uuid):
    comentario = get_object_or_404(ComentarioArtigo.objects, uuid=uuid)
    if comentario.usuario_id == request.user.pk:
        raise PermissionDenied
    motivo = (request.POST.get("motivo") or "").strip()[:500]
    if not motivo:
        messages.error(request, "Informe o motivo da denúncia.")
    else:
        DenunciaComentario.objects.get_or_create(comentario=comentario, usuario=request.user, defaults={"motivo": motivo})
        auditar(request, "DENUNCIAR_COMENTARIO", comentario, motivo=motivo)
        messages.success(request, "Denúncia registrada para análise.")
    return redirect(f"{comentario.artigo.get_absolute_url()}#comentarios")


@login_required
@require_POST
def comentario_moderar(request, uuid):
    if not _can(request.user, "news.moderar_comentarios"):
        raise PermissionDenied
    comentario = get_object_or_404(ComentarioArtigo.all_objects.select_related("artigo"), uuid=uuid)
    status = request.POST.get("status")
    if status not in {ComentarioArtigo.Status.PUBLICADO, ComentarioArtigo.Status.OCULTO, ComentarioArtigo.Status.REJEITADO}:
        raise PermissionDenied
    comentario.status = status
    comentario.moderado_por = request.user
    comentario.moderado_em = timezone.now()
    comentario.motivo_moderacao = (request.POST.get("motivo") or "").strip()[:500]
    comentario.ativo = True
    comentario.excluido_em = None
    comentario.save()
    auditar(request, "MODERAR_COMENTARIO", comentario, motivo=comentario.motivo_moderacao)
    return redirect(f"{comentario.artigo.get_absolute_url()}#comentarios")


def _require_panel(user):
    if not pode(user, "news.acessar_modulo"):
        raise PermissionDenied


def _article_scope(user, *, all_objects=False):
    manager = Artigo.all_objects if all_objects else Artigo.objects
    queryset = manager.select_related("categoria", "autor_editorial", "autor")
    if (
        pode(user, "news.visualizar_artigo_terceiro")
        and escopo_da_permissao(user, "news.visualizar_artigo_terceiro") == AcessoModulo.Escopo.TODOS
    ):
        return queryset
    return queryset.filter(
        Q(autor=user) | Q(autor_editorial__usuario=user)
    )


@login_required
def painel_dashboard(request):
    _require_panel(request.user)
    escopo = _article_scope(request.user)
    agora = timezone.now()
    return render(request, "painel/noticias/dashboard.html", {
        "total": escopo.count(),
        "rascunhos": escopo.filter(status=EditorialStatus.RASCUNHO).count(),
        "revisoes": escopo.filter(status__in=[EditorialStatus.ENVIADO_REVISAO, EditorialStatus.EM_REVISAO]).count(),
        "agendamentos": escopo.filter(status=EditorialStatus.AGENDADO, agendado_para__gte=agora).count(),
        "publicadas": escopo.filter(status=EditorialStatus.PUBLICADO).count(),
        "recentes": escopo[:8],
        "dashboard_cards": [
            (escopo.count(), "Total de artigos"),
            (escopo.filter(status=EditorialStatus.RASCUNHO).count(), "Rascunhos"),
            (escopo.filter(status__in=[EditorialStatus.ENVIADO_REVISAO, EditorialStatus.EM_REVISAO]).count(), "Aguardando revisão"),
            (escopo.filter(status=EditorialStatus.CORRECAO_SOLICITADA).count(), "Devolvidos"),
            (escopo.filter(status=EditorialStatus.APROVADO).count(), "Aprovados"),
            (escopo.filter(status=EditorialStatus.AGENDADO, agendado_para__gte=agora).count(), "Programados"),
            (escopo.filter(status=EditorialStatus.PUBLICADO).count(), "Publicados"),
            (escopo.filter(status=EditorialStatus.ARQUIVADO).count(), "Arquivados"),
            (escopo.filter(Q(autor=request.user) | Q(autor_editorial__usuario=request.user)).count(), "Criados por você"),
            (escopo.filter(status__in=[EditorialStatus.ENVIADO_REVISAO, EditorialStatus.EM_REVISAO, EditorialStatus.APROVADO]).count()
             if pode(request.user, "news.visualizar_artigo_terceiro") else
             escopo.filter(status=EditorialStatus.CORRECAO_SOLICITADA).count(), "Dependem da sua ação"),
        ],
        "news_aux_menu": NEWS_AUX_MENU,
    })


@login_required
def artigo_lista(request, status=None):
    _require_panel(request.user)
    queryset = _article_scope(request.user)
    status = status or request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    if status:
        queryset = queryset.filter(status=status)
    if query:
        queryset = queryset.filter(Q(titulo__icontains=query) | Q(resumo__icontains=query))
    filters = {
        "categoria_id": request.GET.get("categoria"),
        "coluna_id": request.GET.get("coluna"),
        "serie_id": request.GET.get("serie"),
        "autor_editorial_id": request.GET.get("autor"),
    }
    for field, value in filters.items():
        if value:
            queryset = queryset.filter(**{field: value})
    if request.GET.get("proprios") == "1":
        queryset = queryset.filter(Q(autor=request.user) | Q(autor_editorial__usuario=request.user))
    if request.GET.get("inicio"):
        queryset = queryset.filter(atualizado_em__date__gte=request.GET["inicio"])
    if request.GET.get("fim"):
        queryset = queryset.filter(atualizado_em__date__lte=request.GET["fim"])
    page = Paginator(queryset, 20).get_page(request.GET.get("page"))
    for artigo in page.object_list:
        artigo.pode_editar_painel = pode_editar_artigo(request.user, artigo)
    return render(request, "painel/noticias/artigo_list.html", {
        "page_obj": page, "artigos": page.object_list,
        "status_choices": EditorialStatus.choices,
        "categorias": CategoriaNoticia.objects.filter(ativo=True),
        "colunas": Coluna.objects.filter(ativo=True),
        "series": SerieEditorial.objects.filter(ativo=True),
        "autores": Autor.objects.filter(ativo=True, usuario__is_active=True)
        if pode(request.user, "news.visualizar_artigo_terceiro") else (),
        "pode_ver_autores": pode(request.user, "news.visualizar_artigo_terceiro"),
        "news_aux_menu": NEWS_AUX_MENU,
    })


@login_required
def artigo_form(request, uuid=None):
    obj = get_object_or_404(_article_scope(request.user), uuid=uuid) if uuid else None
    if obj:
        if not pode_editar_artigo(request.user, obj):
            raise PermissionDenied
    elif not pode(request.user, "news.criar_artigo"):
        raise PermissionDenied
    form = ArtigoForm(request.POST or None, request.FILES or None, instance=obj, usuario=request.user)
    video_formset = ArtigoVideoFormSet(
        request.POST or None,
        instance=obj or Artigo(),
        prefix="videos",
    )
    requested_status = request.POST.get("status") if request.method == "POST" else None
    if requested_status and requested_status != (obj.status if obj else EditorialStatus.RASCUNHO):
        form.add_error(None, "O estado editorial deve ser alterado pelas ações do fluxo.")
    if request.method == "POST" and form.is_valid() and video_formset.is_valid():
        with transaction.atomic():
            artigo_obj = form.save(commit=False)
            if not artigo_obj.pk:
                artigo_obj.autor = request.user
            if not form.pode_atribuir_autor:
                autor, _ = Autor.objects.get_or_create(
                    usuario=request.user,
                    defaults={"nome": str(request.user), "ativo": True},
                )
                artigo_obj.autor_editorial = autor
            artigo_obj.save()
            form.save_m2m()
            video_formset.instance = artigo_obj
            video_formset.save()
            auditar(
                request, "EDITAR" if obj else "CRIAR", artigo_obj,
                depois={"titulo": artigo_obj.titulo},
            )
        messages.success(request, "Notícia salva.")
        return redirect("painel:news_artigo_editar", uuid=artigo_obj.uuid)
    return render(request, "painel/noticias/artigo_form.html", {
        "form": form, "artigo": obj,
        "video_formset": video_formset,
        "status_choices": EditorialStatus.choices,
        "acoes_status": [
            (status, label) for status, label in EditorialStatus.choices
            if status in TRANSICOES.get(obj.status if obj else EditorialStatus.RASCUNHO, set())
            and (not PERMISSAO_TRANSICAO.get(status) or _can(request.user, PERMISSAO_TRANSICAO[status]))
        ] if obj else [],
        "pode_atribuir_autor": form.pode_atribuir_autor,
        "news_aux_menu": NEWS_AUX_MENU,
    })


@login_required
@require_POST
def artigo_status(request, uuid, status):
    artigo_obj = get_object_or_404(_article_scope(request.user), uuid=uuid)
    try:
        alterar_status(
            artigo=artigo_obj,
            novo_status=status,
            usuario=request.user,
            request=request,
            observacao=request.POST.get("observacao", "")[:2000],
            agendado_para=request.POST.get("agendado_para") or None,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Estado editorial atualizado.")
    return redirect("painel:news_artigo_editar", uuid=uuid)


@login_required
@require_POST
def artigo_excluir(request, uuid):
    if not _can(request.user, "news.excluir"):
        raise PermissionDenied
    obj = get_object_or_404(_article_scope(request.user), uuid=uuid)
    obj.delete()
    auditar(request, "EXCLUIR_LOGICAMENTE", obj)
    return redirect("painel:news_artigo_lista")


@login_required
@require_POST
def artigo_restaurar(request, uuid):
    if not _can(request.user, "news.restaurar"):
        raise PermissionDenied
    obj = get_object_or_404(_article_scope(request.user, all_objects=True), uuid=uuid)
    obj.restore()
    auditar(request, "RESTAURAR", obj)
    return redirect("painel:news_excluidos")


@login_required
def excluidos(request):
    _require_panel(request.user)
    if not _can(request.user, "news.restaurar"):
        raise PermissionDenied
    return render(request, "painel/noticias/excluidos.html", {
        "artigos": _article_scope(request.user, all_objects=True).filter(excluido_em__isnull=False),
        "news_aux_menu": NEWS_AUX_MENU,
    })


AUXILIARES = {
    "autores": (Autor, "news.gerenciar_autores", ["usuario", "nome", "foto", "mini_bio", "biografia", "site", "instagram", "facebook", "linkedin", "x", "tiktok", "youtube", "especialidades", "ativo"]),
    "colunistas": (Colunista, "news.gerenciar_colunistas", ["autor", "titulo", "ordem", "destaque", "ativo"]),
    "colunas": (Coluna, "news.gerenciar_colunas", ["autor", "nome", "descricao", "imagem", "ordem", "ativo"]),
    "categorias": (CategoriaNoticia, "news.gerenciar_categorias", ["nome", "descricao", "categoria_pai", "ordem", "ativo"]),
    "temas": (Tema, "news.gerenciar_temas", ["nome", "descricao", "ativo"]),
    "tags": (Tag, "news.gerenciar_tags", ["nome", "descricao", "ativo"]),
    "especialidades": (EspecialidadeAutor, "news.gerenciar_especialidades", ["nome", "descricao", "ativo"]),
    "series": (SerieEditorial, "news.gerenciar_series", ["nome", "descricao", "imagem", "ordem", "ativo"]),
    "fontes": (ArtigoFonte, "news.gerenciar_fontes", ["artigo", "organizacao", "nome_fonte", "titulo", "url", "tipo", "autor_externo", "data_original", "data_acesso", "observacao", "principal", "verificada", "ordem", "exibir_publicamente", "ativo"]),
    "links": (LinkRelacionado, "news.gerenciar_fontes", ["artigo", "tipo", "rede", "titulo", "url", "nofollow", "ordem", "ativo"]),
    "midias": (MidiaIncorporada, "news.gerenciar_fontes", ["artigo", "episodio", "tipo", "titulo", "url", "ordem", "ativo"]),
    "imagens": (ImagemPublicacao, "news.gerenciar_imagens", ["artigo", "arquivo", "url_externa", "tipo", "titulo", "legenda", "texto_alternativo", "credito", "autor_imagem", "fonte", "url_fonte", "licenca", "url_licenca", "ordem", "capa", "direitos_confirmados", "ativo"]),
    "destaques": (DestaqueEditorial, "news.gerenciar_destaques", ["artigo", "categoria", "posicao", "ordem", "inicio", "fim", "ativo"]),
}


@login_required
def auxiliar_lista(request, tipo):
    if tipo not in AUXILIARES:
        raise PermissionDenied
    model, permissao, _ = AUXILIARES[tipo]
    if not _can(request.user, permissao):
        raise PermissionDenied
    page = Paginator(model.objects.all(), 20).get_page(request.GET.get("page"))
    return render(request, "painel/noticias/auxiliar_list.html", {
        "tipo": tipo, "objetos": page.object_list, "page_obj": page,
        "titulo": model._meta.verbose_name_plural.title(),
        "news_aux_menu": NEWS_AUX_MENU,
    })


@login_required
def auxiliar_form(request, tipo, uuid=None):
    if tipo not in AUXILIARES:
        raise PermissionDenied
    model, permissao, fields = AUXILIARES[tipo]
    if not _can(request.user, permissao):
        raise PermissionDenied
    obj = get_object_or_404(model.objects, uuid=uuid) if uuid else None
    Form = modelform_factory(model, fields=fields)
    form = Form(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        auditar(request, "EDITAR" if uuid else "CRIAR", obj)
        return redirect("painel:news_auxiliar_lista", tipo=tipo)
    return render(request, "painel/noticias/auxiliar_form.html", {
        "tipo": tipo, "form": form, "objeto": obj,
        "news_aux_menu": NEWS_AUX_MENU,
    })


@login_required
def configuracoes(request):
    _require_panel(request.user)
    return render(request, "painel/noticias/configuracoes.html", {
        "news_aux_menu": NEWS_AUX_MENU,
    })


# Compatibilidade com nomes anteriores usados pelos testes e templates.
artigo_novo = artigo_form
artigo_editar = artigo_form
categoria_lista = lambda request: auxiliar_lista(request, "categorias")
categoria_novo = lambda request: auxiliar_form(request, "categorias")
categoria_editar = lambda request, uuid: auxiliar_form(request, "categorias", uuid)
bloco_lista = artigo_lista
bloco_novo = artigo_form
bloco_editar = artigo_form
fonte_lista = lambda request: auxiliar_lista(request, "fontes")
fonte_novo = lambda request: auxiliar_form(request, "fontes")
fonte_editar = lambda request, uuid: auxiliar_form(request, "fontes", uuid)
