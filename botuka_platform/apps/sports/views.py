from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.accounts.permissions import usuario_tem_permissao
from apps.core.domain_views import crud_views
from apps.core.seo.page_builders import listing_seo, sports_seo
from apps.organizations.models import Empresa
from apps.organizations.permissions import usuario_pode_gerenciar_empresa

from .models import (
    Atleta, Campeonato, Categoria, Classificacao, Disputa, Equipe, Estilo,
    Modalidade, OrganizacaoEsportiva, ParticipanteCampeonato,
)


def _permissions(*codes):
    return {"listar": codes, "criar": codes, "editar": codes}


def _global(user):
    return any(usuario_tem_permissao(user, code) for code in ("sports.gerenciar", "sports.criar", "sports.editar", "sports.publicar"))


def _org_from_object(obj):
    if isinstance(obj, OrganizacaoEsportiva):
        return obj
    if isinstance(obj, Equipe):
        return obj.organizacao
    if isinstance(obj, Atleta):
        return obj.equipe.organizacao if obj.equipe_id else None
    campeonato = obj if isinstance(obj, Campeonato) else getattr(obj, "campeonato", None)
    return campeonato.organizacao if campeonato else None


def pode_org(user, obj):
    if _global(user):
        return True
    if isinstance(obj, Atleta) and obj.usuario_id == user.id and usuario_tem_permissao(user, "sports.atleta.editar"):
        return True
    if isinstance(obj, OrganizacaoEsportiva) and obj.empresa_id and not usuario_pode_gerenciar_empresa(user, obj.empresa):
        return False
    org = _org_from_object(obj)
    return bool(org and org.usuario_responsavel_id == user.id)


def escopo_sports(user, queryset):
    if _global(user):
        return queryset
    model = queryset.model
    if model is OrganizacaoEsportiva:
        return queryset.filter(usuario_responsavel=user)
    if model is Equipe:
        return queryset.filter(organizacao__usuario_responsavel=user)
    if model is Atleta:
        return queryset.filter(Q(usuario=user) | Q(equipe__organizacao__usuario_responsavel=user)).distinct()
    if model is Campeonato:
        return queryset.filter(organizacao__usuario_responsavel=user)
    if model in {ParticipanteCampeonato, Disputa, Classificacao}:
        return queryset.filter(campeonato__organizacao__usuario_responsavel=user)
    return queryset.none()


def filtrar_fks_sports(user, form):
    mappings = {
        "organizacao": OrganizacaoEsportiva,
        "equipe": Equipe,
        "campeonato": Campeonato,
        "participante": ParticipanteCampeonato,
        "participante_a": ParticipanteCampeonato,
        "participante_b": ParticipanteCampeonato,
    }
    for field_name, model in mappings.items():
        if field_name in form.fields:
            form.fields[field_name].queryset = escopo_sports(user, model.objects.all())
    if "empresa" in form.fields:
        form.fields["empresa"].queryset = Empresa.objects.all() if _global(user) else Empresa.objects.filter(
            Q(usuario_proprietario=user)
            | Q(usuarios_vinculados__usuario=user, usuarios_vinculados__ativo=True, usuarios_vinculados__excluido_em__isnull=True, usuarios_vinculados__administrador=True)
        ).distinct()


def validar_status_campeonato(user, anterior, novo, obj):
    if anterior == Campeonato.Status.CANCELADO and novo != anterior:
        raise PermissionDenied("Campeonato cancelado não pode ser reaberto por este fluxo.")
    if novo in {Campeonato.Status.EM_ANDAMENTO, Campeonato.Status.FINALIZADO} and not usuario_tem_permissao(user, "sports.publicar") and not usuario_tem_permissao(user, "sports.gerenciar"):
        raise PermissionDenied


def _crud(model, fields, ownership=None, transition=None, permissions=None):
    return crud_views(
        model, "sports", fields, ownership=ownership, scope=escopo_sports,
        filter_form=filtrar_fks_sports, permissions=permissions or {},
        validate_transition=transition,
    )


modalidade_lista, modalidade_novo, modalidade_editar = _crud(Modalidade, ["nome", "descricao", "icone", "imagem", "ordem", "ativo"])
estilo_lista, estilo_novo, estilo_editar = _crud(Estilo, ["modalidade", "nome", "descricao", "ativo"])
categoria_lista, categoria_novo, categoria_editar = _crud(Categoria, ["modalidade", "estilo", "categoria_pai", "nome", "idade_minima", "idade_maxima", "genero", "nivel", "ativo"])
organizacaoesportiva_lista, organizacaoesportiva_novo, organizacaoesportiva_editar = _crud(OrganizacaoEsportiva, ["empresa", "tipo", "nome", "descricao", "logotipo", "cidade", "bairro", "endereco_publico", "telefone", "whatsapp", "email_publico", "site", "ativo"], pode_org, permissions=_permissions("sports.clube.gerenciar"))
equipe_lista, equipe_novo, equipe_editar = _crud(Equipe, ["organizacao", "modalidade", "estilo", "categoria", "nome", "escudo", "treinador", "cidade", "bairro", "ativo"], pode_org, permissions=_permissions("sports.clube.gerenciar", "sports.equipe.gerenciar"))
atleta_lista, atleta_novo, atleta_editar = _crud(Atleta, ["usuario", "equipe", "nome_publico", "apelido", "foto", "modalidade", "estilo", "categoria", "funcao", "numero", "biografia", "publico", "ativo"], pode_org, permissions=_permissions("sports.clube.gerenciar", "sports.equipe.gerenciar", "sports.atleta.editar"))
campeonato_lista, campeonato_novo, campeonato_editar = _crud(Campeonato, ["organizacao", "modalidade", "estilo", "categoria", "nome", "descricao", "regulamento", "formato", "data_inicial", "data_final", "inscricoes_abertas", "inicio_inscricoes", "fim_inscricoes", "status", "imagem", "localidade", "ativo"], pode_org, validar_status_campeonato, _permissions("sports.clube.gerenciar"))
participantecampeonato_lista, participantecampeonato_novo, participantecampeonato_editar = _crud(ParticipanteCampeonato, ["campeonato", "equipe", "atleta", "ativo"], pode_org, permissions=_permissions("sports.clube.gerenciar", "sports.equipe.gerenciar"))
disputa_lista, disputa_novo, disputa_editar = _crud(Disputa, ["campeonato", "fase", "rodada", "tipo", "participante_a", "participante_b", "data_hora", "local", "status", "placar_a", "placar_b", "resultado_textual", "observacoes", "ativo"], pode_org, permissions=_permissions("sports.clube.gerenciar", "sports.equipe.gerenciar", "sports.disputa.arbitrar", "sports.disputa.registrar"))
classificacao_lista, classificacao_novo, classificacao_editar = _crud(Classificacao, ["campeonato", "participante", "jogos", "vitorias", "empates", "derrotas", "pontos", "marcados", "sofridos", "saldo", "posicao", "criterios_adicionais", "ativo"], pode_org, permissions=_permissions("sports.clube.gerenciar", "sports.disputa.registrar"))


PUBLIC_CHAMPIONSHIP_STATUSES = [Campeonato.Status.INSCRICOES, Campeonato.Status.AGENDADO, Campeonato.Status.EM_ANDAMENTO, Campeonato.Status.FINALIZADO]
PUBLIC_DISPUTE_STATUSES = [Disputa.Status.AGENDADA, Disputa.Status.EM_ANDAMENTO, Disputa.Status.ENCERRADA, Disputa.Status.ADIADA, Disputa.Status.WO]


def _public_championships():
    return Campeonato.objects.filter(ativo=True, excluido_em__isnull=True, status__in=PUBLIC_CHAMPIONSHIP_STATUSES, organizacao__ativo=True, organizacao__verificado=True, organizacao__excluido_em__isnull=True)


def _public_disputes():
    return Disputa.objects.filter(ativo=True, excluido_em__isnull=True, status__in=PUBLIC_DISPUTE_STATUSES, campeonato__in=_public_championships())


def home(request):
    now = timezone.now()
    disputes = _public_disputes().select_related("campeonato", "campeonato__modalidade", "participante_a", "participante_a__equipe", "participante_b", "participante_b__equipe").order_by("data_hora")
    championships = _public_championships().select_related("modalidade", "organizacao")
    query = request.GET.get("q", "").strip()[:100]
    if query: championships = championships.filter(Q(nome__icontains=query) | Q(descricao__icontains=query) | Q(localidade__icontains=query) | Q(organizacao__nome__icontains=query))
    if request.GET.get("modalidade"): championships = championships.filter(modalidade__slug=request.GET["modalidade"][:100])
    if request.GET.get("categoria"): championships = championships.filter(categoria__slug=request.GET["categoria"][:100])
    if request.GET.get("local"): championships = championships.filter(localidade__icontains=request.GET["local"][:100])
    if request.GET.get("status") in Campeonato.Status.values: championships = championships.filter(status=request.GET["status"])
    from django.core.paginator import Paginator
    page = Paginator(championships.order_by("data_inicial"), 12).get_page(request.GET.get("page"))
    return render(request, "publico/sports/home.html", {
        "modalidades": Modalidade.objects.filter(ativo=True, excluido_em__isnull=True)[:12],
        "hoje": disputes.filter(data_hora__date=timezone.localdate()),
        "proximas": disputes.filter(data_hora__gt=now)[:8],
        "resultados": disputes.filter(status=Disputa.Status.ENCERRADA).order_by("-data_hora")[:8],
        "campeonatos": page.object_list, "page_obj": page, "total": page.paginator.count,
        "seo": listing_seo(request, 'Esportes em Botucatu | BOTUKA', 'Campeonatos, equipes, atletas e jogos publicados por organizações verificadas.'),
    })


def modalidade(request, slug):
    modalidade_obj = get_object_or_404(Modalidade.objects, slug=slug, ativo=True, excluido_em__isnull=True)
    equipes = Equipe.objects.filter(ativo=True, excluido_em__isnull=True, modalidade=modalidade_obj, organizacao__ativo=True, organizacao__verificado=True, organizacao__excluido_em__isnull=True).select_related("organizacao", "categoria")[:12]
    campeonatos = _public_championships().filter(modalidade=modalidade_obj).select_related("organizacao", "categoria")[:12]
    return render(request, "publico/sports/modalidade.html", {"modalidade": modalidade_obj, "equipes": equipes, "campeonatos": campeonatos, "seo": sports_seo(request, modalidade_obj, kind='modalidade')})


def equipe(request, slug):
    queryset = Equipe.objects.filter(ativo=True, excluido_em__isnull=True, organizacao__ativo=True, organizacao__verificado=True, organizacao__excluido_em__isnull=True).select_related("organizacao", "modalidade", "estilo", "categoria")
    equipe_obj = get_object_or_404(queryset, slug=slug)
    atletas = Atleta.objects.filter(equipe=equipe_obj, publico=True, ativo=True, excluido_em__isnull=True).select_related("modalidade", "categoria")
    return render(request, "publico/sports/equipe.html", {"equipe": equipe_obj, "atletas": atletas, "seo": sports_seo(request, equipe_obj, kind='equipe')})


def atleta(request, uuid):
    queryset = Atleta.objects.filter(publico=True, equipe__organizacao__ativo=True, equipe__organizacao__verificado=True, equipe__organizacao__excluido_em__isnull=True)
    atleta_obj = get_object_or_404(queryset, uuid=uuid)
    return render(request, "publico/sports/atleta.html", {"atleta": atleta_obj, "seo": sports_seo(request, atleta_obj, kind='atleta')})


def campeonato(request, slug):
    campeonato_obj = get_object_or_404(_public_championships().select_related("organizacao", "modalidade", "estilo", "categoria"), slug=slug)
    classificacoes = Classificacao.objects.filter(campeonato=campeonato_obj, ativo=True, excluido_em__isnull=True).select_related("participante", "participante__equipe", "participante__atleta").order_by("posicao")
    jogos = _public_disputes().filter(campeonato=campeonato_obj).select_related("participante_a", "participante_a__equipe", "participante_b", "participante_b__equipe").order_by("data_hora")
    return render(request, "publico/sports/campeonato.html", {"campeonato": campeonato_obj, "share_object": campeonato_obj, "share_type": "campeonato", "classificacoes": classificacoes, "jogos": jogos, "seo": sports_seo(request, campeonato_obj, kind='campeonato')})


def jogo(request, uuid):
    queryset = _public_disputes().select_related("campeonato", "campeonato__modalidade", "participante_a", "participante_a__equipe", "participante_a__atleta", "participante_b", "participante_b__equipe", "participante_b__atleta")
    jogo_obj = get_object_or_404(queryset, uuid=uuid)
    return render(request, "publico/sports/jogo.html", {"jogo": jogo_obj, "seo": sports_seo(request, jogo_obj, kind='jogo')})
