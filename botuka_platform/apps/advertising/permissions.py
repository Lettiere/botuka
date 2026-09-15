from apps.accounts.permissions import usuario_e_master
from apps.organizations.permissions import usuario_pode_gerenciar_empresa


def pode_gerenciar_campanha(usuario, campanha):
    return usuario_e_master(usuario) or usuario_pode_gerenciar_empresa(usuario, campanha.empresa)


def pode_moderar_publicidade(usuario):
    return usuario_e_master(usuario)
