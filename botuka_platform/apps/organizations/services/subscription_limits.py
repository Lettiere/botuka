from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, Sum
from django.utils import timezone

from apps.organizations.models import (
    Assinatura, ContratacaoEmpresaAdicional, Empresa, Plano,
    UsuarioLimitePersonalizado,
)
from apps.organizations.permissions import usuario_pode_gerenciar_empresa


LIMITE_SERVICOS_GRATUITO = 3
EMPRESAS_INCLUSAS_PADRAO = 1


class LimitePlanoExcedido(ValidationError):
    pass


@dataclass(frozen=True)
class ResultadoLimite:
    permitido: bool
    limite: int | None
    total: int
    restante: int | None
    plano_codigo: str
    motivo: str | None = None

    @property
    def utilizado(self):
        return self.total


@dataclass(frozen=True)
class LimitesComerciais:
    limite_empresas: int | None
    limite_servicos: int | None
    plano_codigo: str
    personalizado: bool
    beneficio: UsuarioLimitePersonalizado | None = None


def obter_assinatura_vigente(usuario):
    agora = timezone.now()
    return (Assinatura.objects.select_related('plano', 'empresa_contratante')
        .filter(usuario=usuario, status=Assinatura.Status.ATIVA, ativo=True,
                excluido_em__isnull=True, inicio__lte=agora,
                plano__ativo=True, plano__excluido_em__isnull=True)
        .filter(Q(fim__isnull=True) | Q(fim__gt=agora))
        .order_by('-inicio', '-pk').first())


def _plano_contexto(usuario):
    assinatura = obter_assinatura_vigente(usuario)
    return assinatura, assinatura.plano if assinatura else None


def obter_limite_personalizado_vigente(usuario):
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return None
    agora = timezone.now()
    return (UsuarioLimitePersonalizado.objects.filter(
        usuario=usuario, ativo=True, inicio__lte=agora,
    ).filter(Q(fim__isnull=True) | Q(fim__gt=agora)).first())


def _obter_limite_servicos_plano(usuario):
    assinatura, plano = _plano_contexto(usuario)
    if not plano:
        return LIMITE_SERVICOS_GRATUITO
    if plano.ilimitado_servicos:
        return None
    if assinatura.limite_servicos_contratado is not None:
        return assinatura.limite_servicos_contratado
    return plano.limite_servicos if plano.limite_servicos is not None else LIMITE_SERVICOS_GRATUITO


def obter_limite_servicos(usuario):
    personalizado = obter_limite_personalizado_vigente(usuario)
    if personalizado:
        return None if personalizado.servicos_ilimitados else personalizado.limite_servicos
    return _obter_limite_servicos_plano(usuario)


def total_servicos_utilizados(usuario):
    from apps.services.models import Servico
    return (Servico.all_objects.filter(excluido_em__isnull=True)
        .filter(
            Q(prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA, usuario_responsavel=usuario)
            | Q(prestador_tipo=Servico.PrestadorTipo.EMPRESA, empresa__usuario_proprietario=usuario)
        ).distinct().count())


def usuario_pode_criar_servico(usuario, prestador_tipo=None, empresa=None):
    titular = validar_contexto_servico(usuario, prestador_tipo, empresa) if prestador_tipo else usuario
    assinatura = obter_assinatura_vigente(titular)
    limite = obter_limite_servicos(titular)
    total = total_servicos_utilizados(titular)
    permitido = limite is None or total < limite
    return ResultadoLimite(
        permitido=permitido, limite=limite, total=total,
        restante=None if limite is None else max(limite - total, 0),
        plano_codigo=assinatura.plano.codigo if assinatura else Plano.Codigo.GRATUITO,
        motivo=None if permitido else 'Você atingiu o limite de serviços do seu plano.',
    )


def validar_contexto_servico(usuario, prestador_tipo, empresa=None):
    from apps.services.models import Servico
    if prestador_tipo == Servico.PrestadorTipo.PESSOA_FISICA:
        if empresa is not None:
            raise ValidationError({'empresa': 'Pessoa física não pode vincular uma empresa.'})
        return usuario
    if prestador_tipo != Servico.PrestadorTipo.EMPRESA:
        raise ValidationError({'prestador_tipo': 'Tipo de prestador inválido.'})
    if empresa is None:
        raise ValidationError({'empresa': 'Informe a empresa prestadora.'})
    if not usuario_pode_gerenciar_empresa(usuario, empresa):
        raise PermissionDenied('Você não administra a empresa selecionada.')
    return empresa.usuario_proprietario


def bloquear_e_validar_criacao_servico(usuario, prestador_tipo, empresa=None):
    titular = validar_contexto_servico(usuario, prestador_tipo, empresa)
    get_user_model().objects.select_for_update().get(pk=titular.pk)
    resultado = usuario_pode_criar_servico(usuario, prestador_tipo, empresa)
    if not resultado.permitido:
        raise LimitePlanoExcedido(resultado.motivo)
    return resultado


def total_empresas_ativas(usuario):
    return (Empresa.objects.filter(usuario_proprietario=usuario)
        .values('pk').distinct().count())


def _slots_empresas_adicionais(assinatura):
    if not assinatura:
        return 0
    agora = timezone.now()
    return (ContratacaoEmpresaAdicional.objects.filter(
        assinatura=assinatura, status=ContratacaoEmpresaAdicional.Status.ATIVA,
        ativo=True, excluido_em__isnull=True, inicio__lte=agora,
    ).filter(Q(fim__isnull=True) | Q(fim__gt=agora))
     .aggregate(total=Sum('quantidade'))['total'] or 0)


def obter_limite_empresas(usuario):
    personalizado = obter_limite_personalizado_vigente(usuario)
    if personalizado:
        return None if personalizado.empresas_ilimitadas else personalizado.limite_empresas
    return _obter_limite_empresas_plano(usuario)


def _obter_limite_empresas_plano(usuario):
    assinatura, plano = _plano_contexto(usuario)
    inclusas = plano.empresas_inclusas if plano else EMPRESAS_INCLUSAS_PADRAO
    if plano and plano.ilimitado_empresas:
        return None
    limite = inclusas + _slots_empresas_adicionais(assinatura)
    if plano and plano.limite_empresas is not None:
        limite = min(limite, plano.limite_empresas)
    return limite


def usuario_pode_criar_empresa(usuario):
    assinatura = obter_assinatura_vigente(usuario)
    limite = obter_limite_empresas(usuario)
    total = total_empresas_ativas(usuario)
    permitido = limite is None or total < limite
    return ResultadoLimite(
        permitido=permitido, limite=limite, total=total,
        restante=None if limite is None else max(limite - total, 0),
        plano_codigo=assinatura.plano.codigo if assinatura else Plano.Codigo.GRATUITO,
        motivo=None if permitido else 'Contrate uma empresa adicional para continuar.',
    )


def bloquear_e_validar_criacao_empresa(usuario):
    get_user_model().objects.select_for_update().get(pk=usuario.pk)
    resultado = usuario_pode_criar_empresa(usuario)
    if not resultado.permitido:
        raise LimitePlanoExcedido(resultado.motivo)
    return resultado


class LimiteUsuarioService:
    """Fonte única dos limites comerciais efetivos do usuário."""

    @staticmethod
    def obter_limites(usuario):
        assinatura = obter_assinatura_vigente(usuario)
        beneficio = obter_limite_personalizado_vigente(usuario)
        return LimitesComerciais(
            limite_empresas=obter_limite_empresas(usuario),
            limite_servicos=obter_limite_servicos(usuario),
            plano_codigo=assinatura.plano.codigo if assinatura else Plano.Codigo.GRATUITO,
            personalizado=beneficio is not None,
            beneficio=beneficio,
        )

    @staticmethod
    def obter_limites_do_plano(usuario):
        assinatura = obter_assinatura_vigente(usuario)
        return LimitesComerciais(
            limite_empresas=_obter_limite_empresas_plano(usuario),
            limite_servicos=_obter_limite_servicos_plano(usuario),
            plano_codigo=assinatura.plano.codigo if assinatura else Plano.Codigo.GRATUITO,
            personalizado=False,
        )

    @staticmethod
    def pode_criar_empresa(usuario):
        return usuario_pode_criar_empresa(usuario)

    @staticmethod
    def pode_criar_servico(usuario, prestador_tipo=None, empresa=None):
        return usuario_pode_criar_servico(usuario, prestador_tipo, empresa)

    @staticmethod
    def empresas_restantes(usuario):
        return usuario_pode_criar_empresa(usuario).restante

    @staticmethod
    def servicos_restantes(usuario, prestador_tipo=None, empresa=None):
        return usuario_pode_criar_servico(usuario, prestador_tipo, empresa).restante
