"""Compatibilidade para as regras de assinatura centralizadas no service de domínio."""

from .services.subscription_limits import (
    LimitePlanoExcedido,
    ResultadoLimite,
    bloquear_e_validar_criacao_empresa,
    bloquear_e_validar_criacao_servico,
    obter_assinatura_vigente,
    obter_limite_empresas,
    obter_limite_servicos,
    total_empresas_ativas,
    total_servicos_utilizados,
    usuario_pode_criar_empresa,
    usuario_pode_criar_servico,
    validar_contexto_servico,
)

ResultadoLimiteEmpresa = ResultadoLimite

__all__ = [
    'LimitePlanoExcedido', 'ResultadoLimite', 'ResultadoLimiteEmpresa',
    'bloquear_e_validar_criacao_empresa', 'bloquear_e_validar_criacao_servico',
    'obter_assinatura_vigente', 'obter_limite_empresas', 'obter_limite_servicos',
    'total_empresas_ativas', 'total_servicos_utilizados',
    'usuario_pode_criar_empresa', 'usuario_pode_criar_servico',
    'validar_contexto_servico',
]
