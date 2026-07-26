from django.core.exceptions import PermissionDenied

from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao


ADMIN_PROFILES = ('ADMINISTRADOR', 'ADMIN_GLOBAL')

LEGACY_CODES = {
    'yubotuka.dashboard.visualizar': ('media.gerenciar', 'media.criar', 'media.editar'),
    'yubotuka.video.criar': ('media.criar',),
    'yubotuka.video.editar_proprio': ('media.editar',),
    'yubotuka.video.editar_todos': ('media.gerenciar',),
    'yubotuka.video.enviar_analise': ('media.editar',),
    'yubotuka.video.aprovar': (),
    'yubotuka.video.rejeitar': (),
    'yubotuka.video.publicar': ('media.publicar',),
    'yubotuka.video.agendar': ('media.publicar',),
    'yubotuka.video.arquivar': ('media.gerenciar',),
    'yubotuka.video.destacar': ('media.gerenciar',),
    'yubotuka.canal.gerenciar': ('media.gerenciar',),
    'yubotuka.categoria.gerenciar': ('media.gerenciar',),
    'yubotuka.playlist.gerenciar': ('media.gerenciar',),
    'yubotuka.tag.gerenciar': (),
    'yubotuka.apresentador.gerenciar': (),
    'yubotuka.convidado.gerenciar': (),
    'yubotuka.patrocinador.gerenciar': (),
    'yubotuka.banner.gerenciar': (),
    'yubotuka.motivo_rejeicao.gerenciar': (),
    'yubotuka.config.gerenciar': (),
    'yubotuka.auditoria.visualizar': (),
    'yubotuka.programa.gerenciar': ('media.gerenciar',),
    'yubotuka.temporada.gerenciar': ('media.gerenciar',),
    'yubotuka.episodio.gerenciar': ('media.gerenciar',),
    'yubotuka.transmissao.criar': ('media.transmitir',),
    'yubotuka.transmissao.editar_propria': ('media.transmitir',),
    'yubotuka.transmissao.editar_todas': ('media.gerenciar',),
    'yubotuka.transmissao.enviar_analise': ('media.transmitir',),
    'yubotuka.transmissao.aprovar': (),
    'yubotuka.transmissao.publicar': (),
    'yubotuka.transmissao.cancelar': (),
    'yubotuka.canal.atribuir': (),
    'yubotuka.legado.homologar': (),
}


def e_administrador(user):
    if usuario_e_master(user):
        return True
    return any(user.tem_perfil(nome) for nome in ADMIN_PROFILES)


def possui(user, codigo, *, aceitar_legado=True):
    if e_administrador(user) or usuario_tem_permissao(user, codigo):
        return True
    return aceitar_legado and any(
        usuario_tem_permissao(user, legado)
        for legado in LEGACY_CODES.get(codigo, ())
    )


def exigir(user, codigo, *, aceitar_legado=True):
    if not possui(user, codigo, aceitar_legado=aceitar_legado):
        raise PermissionDenied('Você não possui permissão para esta ação no YuBotuka.')


def pode_editar_video(user, video):
    if possui(user, 'yubotuka.video.editar_todos'):
        return True
    return (
        video.autor_id == user.pk
        and possui(user, 'yubotuka.video.editar_proprio')
        and video.status in {
            video.Status.RASCUNHO,
            video.Status.CORRECAO,
            video.Status.REJEITADO,
        }
    )


def pode_moderar(user):
    return (
        possui(user, 'yubotuka.video.aprovar', aceitar_legado=False)
        or possui(user, 'yubotuka.video.rejeitar', aceitar_legado=False)
    )


def pode_publicar(user):
    return possui(user, 'yubotuka.video.publicar', aceitar_legado=False)
