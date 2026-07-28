"""Serviço central de concessão e revogação de permissões individuais."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.authorization import pode
from apps.accounts.permissions import usuario_e_master
from apps.core.models import PerfilPermissao, Permissao

from .models import AcessoModulo, AuditoriaPermissao, ConcessaoPermissao


def _ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '') if request else ''
    return (forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR')) if request else None


def pode_administrar_permissoes(ator):
    return pode(ator, 'gestao.gerenciar_permissoes')


def _validar(ator, beneficiado, permissao):
    if not pode_administrar_permissoes(ator):
        raise PermissionDenied('Usuário sem autoridade para administrar permissões.')
    if ator.pk == beneficiado.pk:
        raise PermissionDenied('Não é permitido alterar as próprias permissões.')
    if beneficiado.tem_perfil('MASTER') and not usuario_e_master(ator):
        raise PermissionDenied('Permissões de MASTER são protegidas.')
    if permissao.protegida and not usuario_e_master(ator):
        raise PermissionDenied('Apenas MASTER pode administrar esta permissão.')
    if not usuario_e_master(ator) and permissao.criticidade >= Permissao.Criticidade.PROTEGIDA:
        raise PermissionDenied('A permissão excede o nível de autoridade do gestor.')


@transaction.atomic
def conceder_permissao(
    *, ator, beneficiado, permissao, justificativa, request=None,
    valida_ate=None, observacao='', escopo='PROPRIOS', perfil_funcional='',
):
    _validar(ator, beneficiado, permissao)
    if not justificativa.strip():
        raise ValidationError('A justificativa é obrigatória.')
    anterior = {'ativa': beneficiado.tem_permissao(permissao.codigo)}
    modulo = permissao.modulo or permissao.codigo.split('.', 1)[0]
    acesso, _ = AcessoModulo.objects.get_or_create(
        usuario=beneficiado, modulo=modulo,
        defaults={
            'concedido_por': ator, 'valida_ate': valida_ate,
            'justificativa': justificativa, 'observacao': observacao,
            'escopo': escopo,
        },
    )
    concessao, criada = ConcessaoPermissao.objects.get_or_create(
        usuario=beneficiado, permissao=permissao, revogada_em__isnull=True,
        defaults={
            'acesso': acesso,
            'concedida_por': ator, 'valida_ate': valida_ate,
            'justificativa': justificativa, 'observacao': observacao,
            'escopo': escopo, 'perfil_funcional': perfil_funcional,
        },
    )
    if not criada:
        raise ValidationError('O usuário já possui uma concessão ativa.')
    AuditoriaPermissao.objects.create(
        usuario_beneficiado=beneficiado, permissao=permissao, ator=ator,
        acao=AuditoriaPermissao.Acao.CONCEDER, ip=_ip(request),
        justificativa=justificativa, estado_anterior=anterior,
        estado_posterior={'ativa': True, 'valida_ate': valida_ate.isoformat() if valida_ate else None},
    )
    return concessao


@transaction.atomic
def salvar_acesso_modulo(
    *, ator, beneficiado, modulo, permissoes, justificativa, request=None,
    perfil=None, escopo=AcessoModulo.Escopo.PROPRIOS, valida_ate=None,
    observacao='',
):
    if not pode_administrar_permissoes(ator):
        raise PermissionDenied('Usuário sem autoridade para administrar acessos.')
    if ator.pk == beneficiado.pk:
        raise PermissionDenied('Não é permitido alterar os próprios acessos.')
    if not justificativa.strip():
        raise ValidationError('A justificativa é obrigatória.')
    permissoes = list(Permissao.objects.filter(pk__in=[item.pk for item in permissoes], modulo=modulo))
    if not modulo or not Permissao.objects.filter(modulo=modulo, ativo=True).exists():
        raise ValidationError('Módulo inválido ou sem permissões cadastradas.')
    for permissao in permissoes:
        _validar(ator, beneficiado, permissao)
    acesso = AcessoModulo.objects.filter(
        usuario=beneficiado, modulo=modulo,
    ).exclude(status=AcessoModulo.Status.REVOGADO).first()
    created = acesso is None
    if created:
        acesso = AcessoModulo.objects.create(
            usuario=beneficiado, modulo=modulo,
            concedido_por=ator, justificativa=justificativa,
            observacao=observacao,
        )
    anterior = list(acesso.concessoes.filter(revogada_em__isnull=True).values_list('permissao__codigo', flat=True))
    acesso.perfil = perfil
    acesso.escopo = escopo
    acesso.valida_ate = valida_ate
    acesso.observacao = observacao
    acesso.justificativa = justificativa
    acesso.status = AcessoModulo.Status.ATIVO
    acesso.revogado_em = None
    acesso.revogado_por = None
    acesso.save()
    if perfil and created:
        iniciais = Permissao.objects.filter(
            perfil_permissoes__perfil=perfil,
            perfil_permissoes__ativo=True, modulo=modulo,
        )
        permissoes = list({*permissoes, *iniciais})
    selecionadas = {item.pk: item for item in permissoes}
    for concessao in acesso.concessoes.filter(revogada_em__isnull=True).exclude(permissao_id__in=selecionadas):
        revogar_permissao(ator=ator, concessao=concessao, justificativa=justificativa, request=request)
    for permissao in selecionadas.values():
        concessao, created_permission = ConcessaoPermissao.objects.get_or_create(
            usuario=beneficiado, permissao=permissao, revogada_em__isnull=True,
            defaults={
                'acesso': acesso, 'concedida_por': ator, 'valida_ate': valida_ate,
                'justificativa': justificativa, 'observacao': observacao,
                'escopo': escopo, 'perfil_funcional': perfil.nome if perfil else '',
            },
        )
        if not created_permission and concessao.acesso_id != acesso.pk:
            concessao.acesso = acesso
            concessao.save(update_fields=['acesso', 'atualizado_em'])
        if created_permission:
            AuditoriaPermissao.objects.create(
                usuario_beneficiado=beneficiado, permissao=permissao, ator=ator,
                acao=AuditoriaPermissao.Acao.CONCEDER, ip=_ip(request),
                justificativa=justificativa, estado_anterior={'ativa': False},
                estado_posterior={'ativa': True, 'modulo': modulo},
            )
    referencia = acesso.concessoes.select_related('permissao').first()
    if referencia and not created:
        AuditoriaPermissao.objects.create(
            usuario_beneficiado=beneficiado, permissao=referencia.permissao,
            ator=ator, acao=AuditoriaPermissao.Acao.ALTERAR, ip=_ip(request),
            justificativa=justificativa,
            estado_anterior={'modulo': modulo, 'permissoes': anterior},
            estado_posterior={
                'modulo': modulo, 'escopo': escopo,
                'permissoes': [item.codigo for item in selecionadas.values()],
                'valida_ate': valida_ate.isoformat() if valida_ate else None,
            },
        )
    return acesso


@transaction.atomic
def alterar_status_acesso(*, ator, acesso, status, justificativa, request=None):
    if not pode_administrar_permissoes(ator):
        raise PermissionDenied
    if status not in AcessoModulo.Status.values:
        raise ValidationError('Status de acesso inválido.')
    if not justificativa.strip():
        raise ValidationError('A justificativa é obrigatória.')
    anterior = acesso.status
    acesso.status = status
    if status == AcessoModulo.Status.REVOGADO:
        acesso.revogado_em = timezone.now()
        acesso.revogado_por = ator
        for concessao in acesso.concessoes.filter(revogada_em__isnull=True):
            revogar_permissao(ator=ator, concessao=concessao, justificativa=justificativa, request=request)
    acesso.save()
    permissao_referencia = acesso.concessoes.select_related('permissao').first()
    if permissao_referencia:
        AuditoriaPermissao.objects.create(
            usuario_beneficiado=acesso.usuario,
            permissao=permissao_referencia.permissao, ator=ator,
            acao=AuditoriaPermissao.Acao.ALTERAR, ip=_ip(request),
            justificativa=justificativa,
            estado_anterior={'modulo': acesso.modulo, 'status': anterior},
            estado_posterior={'modulo': acesso.modulo, 'status': status},
        )
    return acesso


@transaction.atomic
def revogar_permissao(*, ator, concessao, justificativa, request=None):
    _validar(ator, concessao.usuario, concessao.permissao)
    if concessao.revogada_em:
        raise ValidationError('A concessão já foi revogada.')
    if not justificativa.strip():
        raise ValidationError('A justificativa é obrigatória.')
    concessao.revogada_em = timezone.now()
    concessao.revogada_por = ator
    concessao.save(update_fields=['revogada_em', 'revogada_por', 'atualizado_em'])
    AuditoriaPermissao.objects.create(
        usuario_beneficiado=concessao.usuario, permissao=concessao.permissao,
        ator=ator, acao=AuditoriaPermissao.Acao.REVOGAR, ip=_ip(request),
        justificativa=justificativa, estado_anterior={'ativa': True},
        estado_posterior={'ativa': False, 'revogada_em': concessao.revogada_em.isoformat()},
    )
