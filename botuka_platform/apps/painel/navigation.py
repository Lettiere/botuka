"""Navegação do painel derivada das permissões reais de domínio."""

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from apps.accounts.authorization import criar_verificador_permissoes


def painel_navigation(request, permission_checker=None):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"painel_module_groups": [], "painel_capabilities": {}}
    try:
        reverse('painel:dashboard')
    except NoReverseMatch:
        return {"painel_module_groups": [], "painel_capabilities": {}}
    cached = getattr(request, "_painel_navigation_cache", None)
    if cached is not None:
        return cached
    checker = (
        permission_checker
        or getattr(request, "_painel_permission_checker", None)
        or criar_verificador_permissoes(user)
    )
    request._painel_permission_checker = checker

    def _can(*codes):
        return any(checker(code) for code in codes)

    capabilities = {
        "news_create": _can("news.criar"),
        "news_review": _can("news.revisar"),
        "news_publish": _can("news.publicar"),
        "news_restore": _can("news.restaurar"),
        "news_configure": _can(
            "news.gerenciar", "news.gerenciar_autores",
            "news.gerenciar_categorias", "news.gerenciar_destaques",
        ),
        "account_configure": _can("configuracoes.editar"),
    }

    groups = []

    content = []
    if _can(
        "news.acessar_painel", "news.gerenciar", "news.criar",
        "news.editar", "news.editar_propria", "news.editar_qualquer",
        "news.revisar", "news.publicar",
    ):
        content.append({"label": "BOTUKA News", "icon": "bi-newspaper", "url": reverse("painel:news_dashboard")})
    if _can(
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
            checker("media.transmitir")
            and not _can(
                "yubotuka.dashboard.visualizar", "yubotuka.video.criar",
                "yubotuka.video.editar_proprio", "yubotuka.video.editar_todos",
                "yubotuka.video.aprovar", "yubotuka.video.publicar",
                "media.gerenciar", "media.criar", "media.editar",
                "media.apresentar", "media.publicar",
            )
        )
        route = "painel:media_transmissao_lista" if somente_transmissao else "painel:yubotuka_dashboard"
        content.append({"label": "YoBotuka", "icon": "bi-play-btn-fill", "url": reverse(route)})
    if _can("government.gerenciar", "government.criar", "government.editar", "government.revisar", "government.publicar"):
        content.append({"label": "Prefeitura", "icon": "bi-bank2", "url": reverse("painel:government_dashboard")})
    if _can(
        "TURISMO_LOCAL_VISUALIZAR_PAINEL", "TURISMO_GUIA_VISUALIZAR_PAINEL",
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
    if _can("products.acessar", "products.visualizar"):
        business.append({"label": "Produtos", "icon": "bi-box-seam-fill", "url": reverse("painel:produtos_lista")})
    if _can("products.criar_proprio", "products.criar_empresa"):
        business.append({"label": "Novo produto", "icon": "bi-plus-square-fill", "url": reverse("painel:produto_criar")})
    if _can("products.acessar_conversas"):
        business.append({"label": "Conversas de produtos", "icon": "bi-chat-left-text-fill", "url": reverse("painel:produto_conversas")})
    if _can("products.visualizar_denuncias"):
        business.append({"label": "Denúncias de produtos", "icon": "bi-shield-exclamation", "url": reverse("painel:produto_denuncias")})
    groups.append({"label": "Negócios", "items": business})

    opportunities = []
    if _can("vagas.visualizar", "vagas.criar"):
        opportunities.append({"label": "Vagas", "icon": "bi-briefcase-fill", "url": reverse("painel:vagas_lista")})
    opportunities.extend([
        {"label": "Currículo", "icon": "bi-file-earmark-person-fill", "url": reverse("painel:curriculo")},
        {"label": "Candidaturas", "icon": "bi-person-check-fill", "url": reverse("painel:minhas_candidaturas")},
    ])
    groups.append({"label": "Oportunidades", "items": opportunities})

    if _can("events.acessar", "events.criar_proprio", "events.criar_empresa"):
        groups.append({"label": "Agenda", "items": [
            {"label": "Eventos", "icon": "bi-calendar-event-fill", "url": reverse("painel:eventos_lista")},
        ]})

    groups.append({"label": "Comunidade", "items": [{
        "label": "Rede Social",
        "description": "Feed, conexões e comunidade",
        "icon": "bi-people-fill",
        "url": f"{settings.BOTUKA_SOCIAL_BASE_URL}/social/",
    }]})

    if _can(
        "sports.gerenciar", "sports.criar", "sports.editar", "sports.publicar",
        "sports.clube.gerenciar", "sports.equipe.gerenciar", "sports.disputa.arbitrar",
        "sports.disputa.registrar", "sports.atleta.editar",
    ):
        route = "painel:sports_atleta_lista" if checker("sports.atleta.editar") and not _can(
            "sports.gerenciar", "sports.criar", "sports.editar", "sports.publicar",
            "sports.clube.gerenciar", "sports.equipe.gerenciar", "sports.disputa.arbitrar",
            "sports.disputa.registrar",
        ) else "painel:sports_dashboard"
        groups.append({"label": "Comunidade e atividades", "items": [
            {"label": "Esportes", "icon": "bi-trophy-fill", "url": reverse(route)},
        ]})

    result = {"painel_module_groups": groups, "painel_capabilities": capabilities}
    request._painel_navigation_cache = result
    return result
