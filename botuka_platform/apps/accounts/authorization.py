"""API central de autorização de módulos e objetos da plataforma."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .models import AcessoModulo, ConcessaoPermissao
from .permissions import usuario_e_master


ALIASES = {
    "gestao.acessar": ("usuarios.visualizar",),
    "gestao.gerenciar_usuarios": ("usuarios.criar", "usuarios.editar", "usuarios.visualizar"),
    "gestao.gerenciar_permissoes": ("usuarios.permissoes.gerenciar", "perfis.gerenciar"),
    "news.acessar_modulo": ("news.acessar_painel",),
    "news.acessar": ("news.acessar_modulo", "news.acessar_painel"),
    "news.visualizar": ("news.visualizar_artigo_proprio", "news.acessar_painel"),
    "news.cadastrar": ("news.criar_artigo", "news.criar"),
    "news.editar_proprios": ("news.editar_artigo_proprio", "news.editar_propria"),
    "news.editar_todos": ("news.editar_artigo_terceiro", "news.editar_qualquer"),
    "news.criar_artigo": ("news.criar",),
    "news.editar_artigo_proprio": ("news.editar_propria",),
    "news.editar_artigo_terceiro": ("news.editar_qualquer",),
    "news.visualizar_artigo_proprio": ("news.acessar_painel", "news.editar_propria"),
    "news.visualizar_artigo_terceiro": ("news.editar_qualquer", "news.revisar", "news.publicar"),
    "news.revisar_artigo": ("news.revisar",),
    "news.aprovar_artigo": ("news.aprovar",),
    "news.devolver_correcao": ("news.solicitar_correcao",),
    "news.publicar_artigo": ("news.publicar",),
    "news.despublicar_artigo": ("news.despublicar",),
    "news.agendar_publicacao": ("news.agendar",),
    "news.destacar_artigo": ("news.gerenciar_destaques",),
    "news.arquivar_artigo": ("news.arquivar",),
    "news.restaurar_artigo": ("news.restaurar",),
    "news.atribuir_autor": ("news.gerenciar_autores", "news.editar_qualquer"),
    "news.gerenciar_configuracoes": ("news.gerenciar",),
    "media.acessar": ("media.gerenciar", "media.criar", "media.editar", "media.publicar"),
    "media.visualizar": ("media.editar", "media.publicar"),
    "media.cadastrar": ("media.criar",),
    "media.editar_proprios": ("media.editar",),
    "media.editar_todos": ("media.gerenciar",),
    "events.acessar": ("eventos.visualizar", "eventos.criar"),
    "events.visualizar": ("eventos.visualizar",),
    "events.cadastrar": ("eventos.criar", "events.criar_proprio"),
    "events.criar_proprio": ("eventos.criar",),
    "events.publicar": ("eventos.publicar",),
    "events.editar_proprios": ("eventos.editar",),
    "events.editar_empresa": ("eventos.editar_empresa",),
    "events.moderar": ("eventos.moderar",),
    "products.acessar": ("produtos.visualizar", "produtos.criar"),
    "products.visualizar": ("produtos.visualizar",),
    "products.criar_proprio": ("produtos.criar",),
    "products.editar_proprios": ("produtos.editar",),
    "products.publicar": ("produtos.publicar",),
    "sports.acessar": ("sports.gerenciar", "sports.criar", "sports.editar", "sports.publicar"),
    "sports.visualizar": ("sports.editar", "sports.publicar"),
    "sports.cadastrar": ("sports.criar",),
    "sports.editar_proprios": ("sports.editar",),
    "sports.editar_todos": ("sports.gerenciar",),
}

MODULE_ACCESS_CODES = {
    "news": ("news.acessar", "news.acessar_modulo", "news.acessar_painel"),
    "media": ("media.acessar", "media.gerenciar"),
    "events": ("events.acessar", "eventos.visualizar"),
    "sports": ("sports.acessar", "sports.gerenciar"),
    "products": ("products.acessar", "produtos.visualizar"),
    "gestao": ("gestao.acessar",),
}
MODULE_ALIASES = {"eventos": "events", "produtos": "products"}


def codigos_equivalentes(codigo):
    equivalents = [codigo, *ALIASES.get(codigo, ())]
    equivalents.extend(canonical for canonical, legacy in ALIASES.items() if codigo in legacy)
    return tuple(dict.fromkeys(equivalents))


def criar_verificador_permissoes(usuario):
    """Carrega a autorização do usuário em lote para menus e dashboards."""

    if (
        not usuario
        or not getattr(usuario, "is_authenticated", False)
        or not getattr(usuario, "is_active", False)
    ):
        return lambda codigo: False
    if usuario_e_master(usuario):
        return lambda codigo: True

    from apps.core.models import PerfilPermissao

    profile_ids = set(
        usuario.perfis_adicionais.filter(
            ativo=True, removido_em__isnull=True,
        ).values_list("pk", flat=True)
    )
    if getattr(usuario, "perfil_id", None):
        profile_ids.add(usuario.perfil_id)
    profile_names = set(
        usuario.perfis_adicionais.filter(
            ativo=True, removido_em__isnull=True,
        ).values_list("nome", flat=True)
    )
    if getattr(usuario, "perfil_id", None) and usuario.perfil.ativo and usuario.perfil.removido_em is None:
        profile_names.add(usuario.perfil.nome)
    if any(name.upper() == "ROOT" for name in profile_names):
        return lambda codigo: True

    profile_codes = set(
        PerfilPermissao.objects.filter(
            perfil_id__in=profile_ids,
            ativo=True,
            permissao__ativo=True,
        ).values_list("permissao__codigo", flat=True)
    )
    now = timezone.now()
    accesses = {
        item.modulo: item
        for item in AcessoModulo.objects.filter(
            usuario=usuario,
            status=AcessoModulo.Status.ATIVO,
        ).filter(Q(valida_ate__isnull=True) | Q(valida_ate__gt=now))
    }
    grants_by_module = {}
    for module, code in ConcessaoPermissao.objects.filter(
        usuario=usuario,
        acesso__status=AcessoModulo.Status.ATIVO,
        acesso__revogado_em__isnull=True,
        permissao__ativo=True,
        revogada_em__isnull=True,
    ).filter(
        Q(valida_ate__isnull=True) | Q(valida_ate__gt=now),
    ).filter(
        Q(acesso__valida_ate__isnull=True) | Q(acesso__valida_ate__gt=now),
    ).values_list("acesso__modulo", "permissao__codigo"):
        grants_by_module.setdefault(module, set()).add(code)

    def checker(codigo):
        if not codigo:
            return False
        raw_module = codigo.split(".", 1)[0]
        module = MODULE_ALIASES.get(raw_module, raw_module)
        access_codes = MODULE_ACCESS_CODES.get(module, (f"{module}.acessar",))
        profile_has_access = any(
            equivalent in profile_codes
            for access_code in access_codes
            for equivalent in codigos_equivalentes(access_code)
        )
        if module not in accesses and not profile_has_access:
            return False
        equivalents = set(codigos_equivalentes(codigo))
        return bool(
            equivalents.intersection(profile_codes)
            or equivalents.intersection(grants_by_module.get(module, set()))
        )

    return checker


def _perfil_concede(usuario, codigo):
    checker = getattr(usuario, "tem_permissao", None)
    return bool(checker and any(checker(item) for item in codigos_equivalentes(codigo)))


def acesso_modulo_vigente(usuario, modulo):
    if usuario_e_master(usuario):
        return None
    return (
        AcessoModulo.objects.filter(
            usuario=usuario, modulo=modulo, status=AcessoModulo.Status.ATIVO,
        )
        .filter(Q(valida_ate__isnull=True) | Q(valida_ate__gt=timezone.now()))
        .first()
    )


def pode(usuario, codigo, objeto=None):
    if not usuario or not getattr(usuario, "is_authenticated", False) or not getattr(usuario, "is_active", False):
        return False
    if usuario_e_master(usuario):
        return True
    modulo = MODULE_ALIASES.get(codigo.split(".", 1)[0], codigo.split(".", 1)[0])
    acesso = acesso_modulo_vigente(usuario, modulo)
    acesso_via_perfil = any(
        _perfil_concede(usuario, access_code)
        for access_code in MODULE_ACCESS_CODES.get(modulo, (f"{modulo}.acessar",))
    )
    if not acesso and not acesso_via_perfil:
        return False
    # Perfis globais legados continuam válidos durante a transição. Concessões
    # individuais novas exigem um AcessoModulo vigente.
    via_perfil = _perfil_concede(usuario, codigo)
    via_concessao = ConcessaoPermissao.objects.filter(
        usuario=usuario, acesso=acesso,
        permissao__codigo__in=codigos_equivalentes(codigo),
        revogada_em__isnull=True,
    ).filter(Q(valida_ate__isnull=True) | Q(valida_ate__gt=timezone.now())).exists() if acesso else False
    permitido = via_perfil or via_concessao
    if not permitido:
        return False
    if objeto is None:
        return True
    if usuario_e_proprietario(usuario, objeto):
        return True
    return bool(acesso and acesso.escopo == AcessoModulo.Escopo.TODOS)


def escopo_da_permissao(usuario, codigo):
    if usuario_e_master(usuario):
        return ConcessaoPermissao.Escopo.TODOS
    raw_module = codigo.split(".", 1)[0]
    acesso = acesso_modulo_vigente(usuario, MODULE_ALIASES.get(raw_module, raw_module))
    if acesso:
        return acesso.escopo
    concessao = (
        ConcessaoPermissao.objects.filter(
            usuario=usuario, permissao__codigo__in=codigos_equivalentes(codigo),
            revogada_em__isnull=True,
        )
        .filter(Q(valida_ate__isnull=True) | Q(valida_ate__gt=timezone.now()))
        .order_by("-criado_em")
        .first()
    )
    return concessao.escopo if concessao else ConcessaoPermissao.Escopo.PROPRIOS


def usuario_e_proprietario(usuario, objeto):
    ids = {
        getattr(objeto, "autor_id", None),
        getattr(objeto, "usuario_id", None),
        getattr(objeto, "proprietario_id", None),
        getattr(getattr(objeto, "autor_editorial", None), "usuario_id", None),
    }
    return getattr(usuario, "pk", None) in ids


def pode_visualizar_objeto(usuario, objeto, modulo="news"):
    if usuario_e_proprietario(usuario, objeto):
        return pode(usuario, f"{modulo}.visualizar_artigo_proprio", objeto)
    return pode(usuario, f"{modulo}.visualizar_artigo_terceiro", objeto)


def pode_editar_objeto(usuario, objeto, modulo="news"):
    if usuario_e_proprietario(usuario, objeto):
        return pode(usuario, f"{modulo}.editar_artigo_proprio", objeto)
    return pode(usuario, f"{modulo}.editar_artigo_terceiro", objeto)
