from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core.domain import EditorialStatus
from apps.core.domain_views import crud_views

from .models import Artigo, ArtigoBloco, ArtigoFonte, CategoriaNoticia


NEWS_PERMISSIONS = {"listar": ("news.revisar",), "editar": ("news.revisar",)}


def _editorial(user):
    return any(user.tem_permissao(code) for code in ("news.gerenciar", "news.editar", "news.revisar", "news.publicar"))


def _article_from_object(obj):
    return obj if isinstance(obj, Artigo) else getattr(obj, "artigo", None)


def pode_news(user, obj):
    if isinstance(obj, CategoriaNoticia):
        return user.tem_permissao("news.gerenciar")
    if _editorial(user):
        return True
    artigo = _article_from_object(obj)
    return bool(artigo and artigo.autor_id == user.id)


def escopo_news(user, queryset):
    if _editorial(user):
        return queryset
    if queryset.model is Artigo:
        return queryset.filter(autor=user)
    if queryset.model in {ArtigoBloco, ArtigoFonte}:
        return queryset.filter(artigo__autor=user)
    return queryset.none()


def filtrar_fks_news(user, form):
    if "artigo" in form.fields:
        form.fields["artigo"].queryset = escopo_news(user, Artigo.objects.all())
    if "categoria_pai" in form.fields:
        form.fields["categoria_pai"].queryset = CategoriaNoticia.objects.all()
    if user.tem_permissao("news.revisar") and not any(user.tem_permissao(code) for code in ("news.editar", "news.gerenciar")):
        for name, field in form.fields.items():
            if name not in {"status", "motivo_rejeicao"}:
                field.disabled = True


def validar_estado_news(user, anterior, novo, obj):
    allowed = {
        None: {EditorialStatus.RASCUNHO, EditorialStatus.EM_REVISAO},
        EditorialStatus.RASCUNHO: {EditorialStatus.RASCUNHO, EditorialStatus.EM_REVISAO},
        EditorialStatus.EM_REVISAO: {EditorialStatus.EM_REVISAO, EditorialStatus.APROVADO, EditorialStatus.REJEITADO},
        EditorialStatus.APROVADO: {EditorialStatus.APROVADO, EditorialStatus.PUBLICADO, EditorialStatus.REJEITADO},
        EditorialStatus.PUBLICADO: {EditorialStatus.PUBLICADO, EditorialStatus.PAUSADO},
        EditorialStatus.PAUSADO: {EditorialStatus.PAUSADO, EditorialStatus.PUBLICADO},
        EditorialStatus.REJEITADO: {EditorialStatus.REJEITADO, EditorialStatus.RASCUNHO},
    }
    if novo not in allowed.get(anterior, set()):
        raise PermissionDenied("Transição editorial inválida.")
    if novo in {EditorialStatus.APROVADO, EditorialStatus.REJEITADO} and not (user.tem_permissao("news.revisar") or user.tem_permissao("news.gerenciar")):
        raise PermissionDenied
    if novo in {EditorialStatus.PUBLICADO, EditorialStatus.PAUSADO} and not (user.tem_permissao("news.publicar") or user.tem_permissao("news.gerenciar")):
        raise PermissionDenied


categoria_lista, categoria_novo, categoria_editar = crud_views(CategoriaNoticia, "news", ["nome", "descricao", "categoria_pai", "ordem", "ativo"], ownership=pode_news, scope=escopo_news, filter_form=filtrar_fks_news, permissions=NEWS_PERMISSIONS)
artigo_lista, artigo_novo, artigo_editar = crud_views(Artigo, "news", ["categoria", "titulo", "subtitulo", "resumo", "conteudo", "imagem_capa", "credito_imagem", "fonte", "url_fonte", "data_fato", "status", "destaque", "urgente", "titulo_seo", "descricao_seo", "imagem_social", "campeonato", "acao_publica", "episodio", "ativo"], ownership=pode_news, scope=escopo_news, filter_form=filtrar_fks_news, permissions=NEWS_PERMISSIONS, validate_transition=validar_estado_news)
bloco_lista, bloco_novo, bloco_editar = crud_views(ArtigoBloco, "news", ["artigo", "tipo", "titulo", "conteudo", "url", "ordem", "ativo"], ownership=pode_news, scope=escopo_news, filter_form=filtrar_fks_news, permissions=NEWS_PERMISSIONS)
fonte_lista, fonte_novo, fonte_editar = crud_views(ArtigoFonte, "news", ["artigo", "titulo", "url", "veiculo", "data_acesso", "ordem", "ativo"], ownership=pode_news, scope=escopo_news, filter_form=filtrar_fks_news, permissions=NEWS_PERMISSIONS)


def _published_articles():
    return Artigo.objects.filter(status=EditorialStatus.PUBLICADO, publicado_em__isnull=False, publicado_em__lte=timezone.now(), categoria__ativo=True, categoria__excluido_em__isnull=True).select_related("categoria", "autor")


def home(request):
    queryset = _published_articles()
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(Q(titulo__icontains=query) | Q(resumo__icontains=query) | Q(conteudo__icontains=query))
    page = Paginator(queryset, 12).get_page(request.GET.get("page"))
    return render(request, "publico/news/home.html", {"artigos": page.object_list, "page_obj": page, "total": page.paginator.count, "categorias": CategoriaNoticia.objects.filter(ativo=True, excluido_em__isnull=True)})


def categoria(request, slug):
    category = get_object_or_404(CategoriaNoticia.objects, slug=slug)
    queryset = _published_articles().filter(categoria=category)
    query = request.GET.get("q", "").strip()[:100]
    if query: queryset = queryset.filter(Q(titulo__icontains=query) | Q(resumo__icontains=query) | Q(conteudo__icontains=query))
    page = Paginator(queryset, 12).get_page(request.GET.get("page"))
    return render(request, "publico/news/home.html", {"categoria": category, "artigos": page.object_list, "page_obj": page, "total": page.paginator.count, "categorias": CategoriaNoticia.objects.filter(ativo=True, excluido_em__isnull=True)})


def artigo(request, slug):
    obj = get_object_or_404(_published_articles(), slug=slug)
    related = _published_articles().filter(categoria=obj.categoria).exclude(pk=obj.pk)[:4]
    return render(request, "publico/news/artigo.html", {"artigo": obj, "relacionados": related})
