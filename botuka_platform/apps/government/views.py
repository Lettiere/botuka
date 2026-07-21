from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from apps.core.domain import EditorialStatus
from apps.core.domain_views import crud_views
from apps.core.seo.page_builders import government_seo, listing_seo

from .models import AcaoAtualizacao, AcaoDocumento, AcaoLink, AcaoPublica, OrgaoPublico, OrgaoUsuario


GOV_PERMISSIONS = {
    "listar": ("government.revisar",),
    "editar": ("government.revisar",),
}


def _global(user):
    return user.tem_permissao("government.gerenciar")


def _orgaos_do_usuario(user):
    return OrgaoPublico.objects.filter(
        usuarios_vinculados__usuario=user,
        usuarios_vinculados__ativo=True,
        usuarios_vinculados__excluido_em__isnull=True,
    ).distinct()


def _orgao_from_object(obj):
    if isinstance(obj, OrgaoPublico):
        return obj
    if isinstance(obj, AcaoPublica):
        return obj.orgao
    acao = getattr(obj, "acao", None)
    return acao.orgao if acao else None


def pode_org(user, obj):
    if _global(user):
        return True
    orgao = _orgao_from_object(obj)
    if not orgao:
        return False
    vinculo = OrgaoUsuario.objects.filter(
        orgao=orgao, usuario=user, ativo=True, excluido_em__isnull=True
    )
    if isinstance(obj, OrgaoPublico):
        return vinculo.filter(gestor=True).exists()
    return vinculo.filter(Q(gestor=True) | Q(editor=True) | Q(revisor=True)).exists()


def escopo_government(user, queryset):
    if _global(user):
        return queryset
    orgaos = _orgaos_do_usuario(user)
    model = queryset.model
    if model is OrgaoPublico:
        return queryset.filter(pk__in=orgaos)
    if model is AcaoPublica:
        return queryset.filter(orgao__in=orgaos)
    if model in {AcaoAtualizacao, AcaoDocumento, AcaoLink}:
        return queryset.filter(acao__orgao__in=orgaos)
    return queryset.none()


def filtrar_fks_government(user, form):
    if "orgao" in form.fields:
        form.fields["orgao"].queryset = _orgaos_do_usuario(user) if not _global(user) else OrgaoPublico.objects.all()
    if "acao" in form.fields:
        form.fields["acao"].queryset = escopo_government(user, AcaoPublica.objects.all())
    if user.tem_permissao("government.revisar") and not any(user.tem_permissao(code) for code in ("government.editar", "government.gerenciar")):
        for name, field in form.fields.items():
            if name not in {"status", "motivo_rejeicao"}:
                field.disabled = True


def validar_estado_government(user, anterior, novo, obj):
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
    if novo in {EditorialStatus.APROVADO, EditorialStatus.REJEITADO} and not (user.tem_permissao("government.revisar") or _global(user)):
        raise PermissionDenied
    if novo in {EditorialStatus.PUBLICADO, EditorialStatus.PAUSADO}:
        if _global(user):
            return
        orgao = _orgao_from_object(obj)
        autorizado = OrgaoUsuario.objects.filter(
            orgao=orgao,
            usuario=user,
            ativo=True,
            excluido_em__isnull=True,
            pode_publicar=True,
        ).exists()
        if not user.tem_permissao("government.publicar") or not autorizado:
            raise PermissionDenied


def _crud(model, fields, ownership=True, transition=None):
    return crud_views(model, "government", fields, ownership=pode_org if ownership else None, scope=escopo_government, filter_form=filtrar_fks_government, permissions=GOV_PERMISSIONS, validate_transition=transition)


orgao_lista, orgao_novo, orgao_editar = _crud(OrgaoPublico, ["tipo", "nome", "sigla", "descricao", "logotipo", "site_oficial", "telefone", "email", "ativo"])
acao_lista, acao_novo, acao_editar = _crud(AcaoPublica, ["orgao", "tipo", "titulo", "resumo", "descricao", "objetivo", "publico_alvo", "local", "bairro", "cidade", "inicio_previsto", "conclusao_prevista", "situacao", "status", "imagem", "destaque", "ativo"], transition=validar_estado_government)
atualizacao_lista, atualizacao_novo, atualizacao_editar = _crud(AcaoAtualizacao, ["acao", "titulo", "descricao", "percentual", "data", "imagem", "ordem", "ativo"])
documento_lista, documento_novo, documento_editar = _crud(AcaoDocumento, ["acao", "titulo", "tipo", "arquivo", "ordem", "ativo"])
link_lista, link_novo, link_editar = _crud(AcaoLink, ["acao", "titulo", "url", "tipo", "ordem", "ativo"])


def _public_actions():
    return AcaoPublica.objects.filter(ativo=True, excluido_em__isnull=True, status=EditorialStatus.PUBLICADO, publicado_em__isnull=False, orgao__verificado=True, orgao__ativo=True, orgao__excluido_em__isnull=True).select_related("orgao")


def home(request):
    queryset = _public_actions().order_by("-destaque", "-publicado_em")
    query = request.GET.get("q", "").strip()[:100]
    if query: queryset = queryset.filter(Q(titulo__icontains=query) | Q(resumo__icontains=query) | Q(descricao__icontains=query) | Q(orgao__nome__icontains=query) | Q(bairro__icontains=query))
    if request.GET.get("tipo") in AcaoPublica.Tipo.values: queryset = queryset.filter(tipo=request.GET["tipo"])
    if request.GET.get("bairro"): queryset = queryset.filter(bairro__iexact=request.GET["bairro"][:100])
    if request.GET.get("situacao") in AcaoPublica.Situacao.values: queryset = queryset.filter(situacao=request.GET["situacao"])
    from django.core.paginator import Paginator
    page = Paginator(queryset, 12).get_page(request.GET.get("page"))
    seo = listing_seo(request, 'Prefeitura e órgãos públicos de Botucatu | BOTUKA', 'Ações, serviços e publicações de órgãos públicos verificados de Botucatu.')
    return render(request, "publico/government/home.html", {"acoes": page.object_list, "page_obj": page, "total": page.paginator.count, "orgaos": OrgaoPublico.objects.filter(verificado=True, ativo=True, excluido_em__isnull=True), "seo": seo})


def orgao(request, slug):
    orgao_obj = get_object_or_404(OrgaoPublico.objects, slug=slug, verificado=True, ativo=True, excluido_em__isnull=True)
    acoes_orgao = _public_actions().filter(orgao=orgao_obj).order_by("-publicado_em")[:12]
    return render(request, "publico/government/orgao.html", {"orgao": orgao_obj, "acoes": acoes_orgao, "seo": government_seo(request, orgao_obj, kind='orgao')})


def acoes(request):
    return home(request)


def acao(request, slug):
    acao_obj = get_object_or_404(_public_actions(), slug=slug)
    atualizacoes = acao_obj.atualizacoes.filter(ativo=True, excluido_em__isnull=True).select_related("autor").order_by("-data", "ordem")
    documentos = acao_obj.documentos.filter(ativo=True, excluido_em__isnull=True).order_by("ordem")
    links = acao_obj.links.filter(ativo=True, excluido_em__isnull=True).order_by("ordem")
    return render(request, "publico/government/acao.html", {"acao": acao_obj, "atualizacoes": atualizacoes, "documentos": documentos, "links": links, "seo": government_seo(request, acao_obj)})
