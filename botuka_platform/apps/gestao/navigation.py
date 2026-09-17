"""Árvore de navegação administrativa resolvida uma vez por request."""

from django.urls import reverse

from apps.accounts.authorization import criar_verificador_permissoes
from apps.accounts.permissions import usuario_e_master


def _item(label, icon, url, *, names=(), kind=""):
    return {
        "label": label, "icon": icon, "url": url,
        "names": set(names), "kind": kind, "active": False,
    }


def gestao_navigation(request):
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return {"gestao_navigation": []}

    can = criar_verificador_permissoes(user)
    master = usuario_e_master(user)
    groups = [{
        "label": "Visão geral", "icon": "bi-grid",
        "items": [_item("Dashboard", "bi-speedometer2", reverse("gestao:dashboard"), names=("dashboard",))],
    }]

    registrations = []
    if can("empresas.gerenciar"):
        registrations.extend([
            _item("Empresas", "bi-buildings", reverse("gestao:empresas_lista"),
                  names=("empresas_lista", "empresa_detalhe", "empresa_nova", "empresa_editar", "empresa_inativar", "empresa_reativar", "empresa_vinculo_novo", "empresa_vinculo_editar", "empresa_vinculo_inativar", "empresa_vinculo_reativar", "empresa_capacidade_analisar")),
            _item("Solicitações", "bi-inbox", reverse("gestao:solicitacoes_lista"),
                  names=("solicitacoes_lista", "solicitacao_detalhe", "solicitacao_analisar")),
        ])
    if can("usuarios.visualizar"):
        registrations.append(_item(
            "Usuários", "bi-people", reverse("gestao:usuarios_lista"),
            names=("usuarios_lista", "usuarios_detalhe", "usuarios_novo", "usuarios_editar", "usuarios_ativar", "usuarios_desativar", "usuario_acessos", "usuario_acesso_novo", "usuario_acesso_editar", "usuario_acesso_status", "usuario_permissoes"),
        ))
    if can("perfis.gerenciar"):
        registrations.append(_item(
            "Perfis e permissões", "bi-person-lock", reverse("gestao:perfis_lista"),
            names=("perfis_lista", "perfis_novo", "perfis_editar", "perfil_permissoes", "permissoes_lista", "permissoes_novo", "permissoes_editar", "controle_detalhe", "controle_status"),
        ))
    if can("categorias.gerenciar"):
        registrations.extend([
            _item("Taxonomia empresarial", "bi-diagram-3", reverse("gestao:categorias_lista"),
                  names=("categorias_lista", "categorias_novo", "categorias_editar", "subcategorias_lista", "subcategorias_novo", "subcategorias_editar")),
            _item("CNAEs e mapeamentos", "bi-list-nested", reverse("gestao:taxonomia_empresarial_lista", args=["cnaes"]),
                  names=("taxonomia_empresarial_lista", "taxonomia_empresarial_detalhe", "taxonomia_empresarial_novo", "taxonomia_empresarial_editar", "taxonomia_empresarial_status")),
            _item("Taxonomia de produtos", "bi-boxes", reverse("gestao:taxonomia_produtos_dashboard"),
                  names=("taxonomia_produtos_dashboard",)),
        ])
    if can("localidades.gerenciar"):
        registrations.append(_item(
            "Localidades", "bi-geo-alt", reverse("gestao:paises_lista"),
            names=("paises_lista", "paises_novo", "paises_editar", "estados_lista", "estados_novo", "estados_editar", "cidades_lista", "cidades_novo", "cidades_editar", "bairros_lista", "bairros_novo", "bairros_editar", "localidade_detalhe", "localidade_status"),
        ))
    if registrations:
        groups.append({"label": "Cadastros", "icon": "bi-database", "items": registrations})

    if master:
        central_groups = (
            ("Conteúdo", "bi-file-earmark-text", (("Artigos", "bi-newspaper", "artigos"), ("Eventos", "bi-calendar-event", "eventos"), ("Vídeos", "bi-play-btn", "videos"), ("Turismo", "bi-compass", "turismo"))),
            ("Negócios", "bi-briefcase", (("Produtos", "bi-box-seam", "produtos"), ("Serviços", "bi-tools", "servicos"), ("Agendamentos", "bi-calendar-check", "agendamentos"), ("Vagas", "bi-person-workspace", "vagas"))),
            ("Financeiro", "bi-wallet2", (("Cobranças", "bi-receipt", "cobrancas"), ("Pagamentos", "bi-credit-card", "pagamentos"), ("Transações", "bi-arrow-left-right", "transacoes"), ("Webhooks", "bi-broadcast", "webhooks"))),
        )
        for label, icon, specs in central_groups:
            groups.append({"label": label, "icon": icon, "items": [
                _item(item_label, item_icon, reverse("gestao:central_lista", args=[kind]),
                      names=("central_lista", "central_detalhe"), kind=kind)
                for item_label, item_icon, kind in specs
            ]})
        groups.insert(-1, {"label": "Publicidade", "icon": "bi-megaphone", "items": [
            _item(
                "Moderação de campanhas",
                "bi-shield-check",
                reverse("gestao:publicidade_campanhas"),
                names=(
                    "publicidade_campanhas",
                    "publicidade_campanha_detalhe",
                    "publicidade_campanha_aprovar",
                    "publicidade_campanha_moderar",
                ),
            ),
            _item(
                "Planos e posições",
                "bi-sliders",
                reverse("gestao:publicidade_configuracao"),
                names=(
                    "publicidade_configuracao",
                    "publicidade_plano_novo",
                    "publicidade_plano_editar",
                    "publicidade_posicionamento_novo",
                    "publicidade_posicionamento_editar",
                ),
            ),
            _item("Criativos", "bi-image", reverse("gestao:publicidade_criativos"), names=("publicidade_criativos", "publicidade_criativo_detalhe")),
            _item("Entregas", "bi-bar-chart", reverse("gestao:publicidade_entregas"), names=("publicidade_entregas",)),
        ]})
        groups.append({"label": "Inteligência", "icon": "bi-graph-up", "items": [
            _item("Analytics GA4", "bi-google", reverse("gestao:analytics_ga4"), names=("analytics_ga4",)),
            _item("Analytics interno", "bi-activity", reverse("gestao:central_lista", args=["analytics-eventos"]), names=("central_lista", "central_detalhe"), kind="analytics-eventos"),
            _item("Auditoria", "bi-journal-check", reverse("gestao:central_lista", args=["auditoria"]), names=("central_lista", "central_detalhe"), kind="auditoria"),
        ]})

    system = []
    if can("contatos.visualizar"):
        system.append(_item("Contatos", "bi-person-lines-fill", reverse("gestao:contatos_lista"), names=("contatos_lista", "contatos_novo", "contatos_editar", "contatos_ativar", "contatos_desativar")))
    if can("configuracoes.gerenciar"):
        system.append(_item("Configurações", "bi-gear", reverse("gestao:configuracoes_lista"), names=("configuracoes_lista", "configuracoes_novo", "configuracoes_editar")))
    if system:
        groups.append({"label": "Sistema", "icon": "bi-gear-wide-connected", "items": system})

    match = getattr(request, "resolver_match", None)
    current_name = getattr(match, "url_name", "")
    current_kind = (getattr(match, "kwargs", {}) or {}).get("kind", "")
    active_found = False
    for group in groups:
        group["active"] = False
        for item in group["items"]:
            item["active"] = current_name in item["names"] and (not item["kind"] or item["kind"] == current_kind)
            if item["active"] and not active_found:
                group["active"] = active_found = True
            elif item["active"]:
                item["active"] = False
    return {"gestao_navigation": groups}
