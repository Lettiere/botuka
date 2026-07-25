from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.organizations.permissions import usuario_pode_publicar_por_empresa

from ..models import Vaga, VagaAuditoria
from ..permissions import pode_administrar_vaga


TRANSICOES = {
    Vaga.Status.RASCUNHO: {Vaga.Status.EM_ANALISE, Vaga.Status.PUBLICADA},
    Vaga.Status.EM_ANALISE: {Vaga.Status.PUBLICADA, Vaga.Status.REJEITADA},
    Vaga.Status.PUBLICADA: {Vaga.Status.PAUSADA, Vaga.Status.ENCERRADA},
    Vaga.Status.PAUSADA: {Vaga.Status.PUBLICADA, Vaga.Status.ENCERRADA},
    Vaga.Status.ENCERRADA: {Vaga.Status.PUBLICADA},
    Vaga.Status.EXPIRADA: {Vaga.Status.PUBLICADA, Vaga.Status.ENCERRADA},
    Vaga.Status.REJEITADA: {Vaga.Status.RASCUNHO, Vaga.Status.EM_ANALISE},
}


def ip_da_requisicao(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')) or None


def registrar_acao(vaga, usuario, acao, request=None, **contexto):
    return VagaAuditoria.objects.create(
        vaga=vaga, usuario=usuario, acao=acao, contexto=contexto,
        ip=ip_da_requisicao(request) if request else None,
    )


def configurar_responsavel(vaga, usuario, empresa=None):
    vaga.usuario_criador_id = vaga.usuario_criador_id or usuario.id
    vaga.usuario_responsavel_id = vaga.usuario_responsavel_id or usuario.id
    if empresa:
        if not usuario_pode_publicar_por_empresa(usuario, empresa):
            raise ValidationError('Você não possui autorização para publicar por esta empresa.')
        vaga.empresa = empresa
        vaga.perfil_pessoa_fisica = None
    else:
        if not usuario.perfil_contratante_completo:
            raise ValidationError(
                'Para publicar como pessoa física, complete CPF validado, contato, '
                'localização e aceite dos termos.'
            )
        vaga.empresa = None
        vaga.perfil_pessoa_fisica = usuario
    return vaga


def alterar_status(vaga, usuario, novo_status, request=None):
    if not pode_administrar_vaga(usuario, vaga):
        raise ValidationError('Você não pode administrar esta vaga.')
    if novo_status not in TRANSICOES.get(vaga.status, set()):
        raise ValidationError('Transição de status não permitida.')
    anterior = vaga.status
    vaga.status = novo_status
    if novo_status == Vaga.Status.PUBLICADA:
        vaga.publicado_em = timezone.now()
    vaga.save()
    registrar_acao(vaga, usuario, novo_status.lower(), request, status_anterior=anterior)
    return vaga
