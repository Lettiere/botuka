"""Navegação do painel derivada das permissões reais de domínio."""

from django.urls import reverse
from apps.accounts.permissions import usuario_tem_permissao


def _can(user, *codes):
    return any(usuario_tem_permissao(user, code) for code in codes)


def painel_navigation(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"painel_module_groups": [], "painel_capabilities": {}}

    capabilities = {
        "news_create": _can(user, "news.criar"),
        "news_review": _can(user, "news.revisar"),
        "news_publish": _can(user, "news.publicar"),
        "news_restore": _can(user, "news.restaurar"),
        "news_configure": _can(
            user, "news.gerenciar", "news.gerenciar_autores",
            "news.gerenciar_categorias", "news.gerenciar_destaques",
        ),
        "account_configure": _can(user, "configuracoes.editar"),
    }

    groups = []

    content = []
    if _can(
        user, "news.acessar_painel", "news.gerenciar", "news.criar",
        "news.editar", "news.editar_propria", "news.editar_qualquer",
        "news.revisar", "news.publicar",
    ):
        content.append({"label": "BOTUKA News", "icon": "bi-newspaper", "url": reverse("painel:news_dashboard")})
    if _can(
        user,
        "yubotuka.dashboard.visualizar", "yubotuka.video.criar",
        "yubotuka.video.editar_proprio", "yubotuka.video.editar_todos",
        "yubotuka.video.aprovar", "yubotuka.video.publicar",
        "yubotuka.programa.gerenciar", "yubotuka.temporada.gerenciar",
        "yubotuka.episodio.gerenciar", "yubotuka.transmissao.criar",
        "yubotuka.transmissao.editar_propria", "yubotuka.transmissao.editar_todas",
        "yubotuka.transmissao.aprovar", "yubotuka.transmissao.publicar",
        "yubotuka.canal.atribuir", "yubotuka.legado.homologar",
        "media.gerenciar", "media.criar", "media.editar",
        "media.apresentar", "media.transmitir", "media.publicar",
    ):
        somente_transmissao = (
            usuario_tem_permissao(user, "media.transmitir")
            and not _can(
                user,
                "yubotuka.dashboard.visualizar", "yubotuka.video.criar",
                "yubotuka.video.editar_proprio", "yubotuka.video.editar_todos",
                "yubotuka.video.aprovar", "yubotuka.video.publicar",
                "media.gerenciar", "media.criar", "media.editar",
                "media.apresentar", "media.publicar",
            )
        )
        route = "painel:media_transmissao_lista" if somente_transmissao else "painel:yubotuka_dashboard"
        content.append({"label": "YuBotuka", "icon": "bi-play-btn-fill", "url": reverse(route)})
    if _can(user, "government.gerenciar", "government.criar", "government.editar", "government.revisar", "government.publicar"):
        content.append({"label": "Prefeitura", "icon": "bi-bank2", "url": reverse("painel:government_dashboard")})
    if _can(
        user, "TURISMO_LOCAL_VISUALIZAR_PAINEL", "TURISMO_GUIA_VISUALIZAR_PAINEL",
        "TURISMO_LOCAL_CADASTRAR", "TURISMO_GUIA_CADASTRAR",
        "TURISMO_VIDEO_CADASTRAR", "TURISMO_PLAYLIST_CADASTRAR",
    ):
        content.append({"label": "Turismo", "icon": "bi-binoculars-fill", "url": reverse("painel:turismo_dashboard")})
    if content:
        groups.append({"label": "Conteúdo da cidade", "items": content})

    business = [
        {"label": "Empresas", "icon": "bi-buildings-fill", "url": reverse("painel:empresas_lista")},
        {"label": "Serviços", "icon": "bi-tools", "url": reverse("painel:servicos_lista")},
    ]
    groups.append({"label": "Negócios", "items": business})

    opportunities = []
    if _can(user, "vagas.visualizar", "vagas.criar"):
        opportunities.append({"label": "Vagas", "icon": "bi-briefcase-fill", "url": reverse("painel:vagas_lista")})
    opportunities.extend([
        {"label": "Currículo", "icon": "bi-file-earmark-person-fill", "url": reverse("painel:curriculo")},
        {"label": "Candidaturas", "icon": "bi-person-check-fill", "url": reverse("painel:minhas_candidaturas")},
    ])
    groups.append({"label": "Oportunidades", "items": opportunities})

    if _can(user, "eventos.visualizar", "eventos.criar"):
        groups.append({"label": "Agenda", "items": [
            {"label": "Eventos", "icon": "bi-calendar-event-fill", "url": reverse("painel:eventos_lista")},
        ]})

    community = []
    if _can(user, "publicacoes.visualizar"):
        community.append({"label": "Publicações", "icon": "bi-megaphone-fill", "url": reverse("painel:publicacoes_lista")})
    if _can(user, "rede_social.acessar"):
        community.append({"label": "Rede social", "icon": "bi-share-fill", "url": reverse("painel:rede_social")})
    if _can(user, "mensagens.acessar"):
        community.append({"label": "Mensagens", "icon": "bi-chat-dots-fill", "url": reverse("painel:mensagens")})
    if community:
        groups.append({"label": "Comunidade", "items": community})

    if _can(
        user, "sports.gerenciar", "sports.criar", "sports.editar", "sports.publicar",
        "sports.clube.gerenciar", "sports.equipe.gerenciar", "sports.disputa.arbitrar",
        "sports.disputa.registrar", "sports.atleta.editar",
    ):
        route = "painel:sports_atleta_lista" if usuario_tem_permissao(user, "sports.atleta.editar") and not _can(
            user, "sports.gerenciar", "sports.criar", "sports.editar", "sports.publicar",
            "sports.clube.gerenciar", "sports.equipe.gerenciar", "sports.disputa.arbitrar",
            "sports.disputa.registrar",
        ) else "painel:sports_dashboard"
        groups.append({"label": "Comunidade e atividades", "items": [
            {"label": "Esportes", "icon": "bi-trophy-fill", "url": reverse(route)},
        ]})

    return {"painel_module_groups": groups, "painel_capabilities": capabilities}
