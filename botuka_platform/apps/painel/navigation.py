"""Navegação do painel derivada das permissões reais de domínio."""

from django.urls import reverse


def _can(user, *codes):
    return any(user.tem_permissao(code) for code in codes)


def painel_navigation(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"painel_module_groups": []}

    groups = []

    content = []
    if _can(user, "news.gerenciar", "news.criar", "news.editar", "news.revisar", "news.publicar"):
        content.append({"label": "BOTUKA News", "icon": "bi-newspaper", "url": reverse("painel:news_dashboard")})
    if _can(user, "media.gerenciar", "media.criar", "media.editar", "media.apresentar", "media.transmitir", "media.publicar"):
        route = "painel:media_transmissao_lista" if user.tem_permissao("media.transmitir") and not _can(user, "media.gerenciar", "media.criar", "media.editar", "media.apresentar", "media.publicar") else "painel:ytv_dashboard"
        content.append({"label": "YTv Botuka", "icon": "bi-play-btn-fill", "url": reverse(route)})
    if _can(user, "government.gerenciar", "government.criar", "government.editar", "government.revisar", "government.publicar"):
        content.append({"label": "Prefeitura", "icon": "bi-bank2", "url": reverse("painel:government_dashboard")})
    if content:
        groups.append({"label": "Conteúdo da cidade", "items": content})

    opportunities = []
    if _can(user, "vagas.visualizar", "vagas.criar"):
        opportunities.append({"label": "Vagas", "icon": "bi-briefcase-fill", "url": reverse("painel:vagas_lista")})
    opportunities.extend([
        {"label": "Currículo", "icon": "bi-file-earmark-person-fill", "url": reverse("painel:curriculo")},
        {"label": "Candidaturas", "icon": "bi-person-check-fill", "url": reverse("painel:minhas_candidaturas")},
    ])
    groups.append({"label": "Oportunidades", "items": opportunities})

    if _can(
        user, "sports.gerenciar", "sports.criar", "sports.editar", "sports.publicar",
        "sports.clube.gerenciar", "sports.equipe.gerenciar", "sports.disputa.arbitrar",
        "sports.disputa.registrar", "sports.atleta.editar",
    ):
        route = "painel:sports_atleta_lista" if user.tem_permissao("sports.atleta.editar") and not _can(
            user, "sports.gerenciar", "sports.criar", "sports.editar", "sports.publicar",
            "sports.clube.gerenciar", "sports.equipe.gerenciar", "sports.disputa.arbitrar",
            "sports.disputa.registrar",
        ) else "painel:sports_dashboard"
        groups.append({"label": "Comunidade e atividades", "items": [
            {"label": "Esportes", "icon": "bi-trophy-fill", "url": reverse(route)},
        ]})

    return {"painel_module_groups": groups}
