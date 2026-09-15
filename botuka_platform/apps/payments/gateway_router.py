from .models import Cobranca


GATEWAY_BY_ORIGIN = {
    Cobranca.Origem.PUBLICIDADE: 'c6', Cobranca.Origem.MENSALIDADE: 'c6',
    Cobranca.Origem.PLANO: 'c6', Cobranca.Origem.ASSINATURA: 'c6',
    Cobranca.Origem.COBRANCA_INSTITUCIONAL: 'c6', Cobranca.Origem.PRODUTO: 'mercado_pago',
    Cobranca.Origem.SERVICO: 'mercado_pago', Cobranca.Origem.PRESTACAO_SERVICO: 'mercado_pago',
}


def gateway_code_for(origem: str) -> str:
    try:
        return GATEWAY_BY_ORIGIN[origem]
    except KeyError as exc:
        raise ValueError(f'Origem de cobrança desconhecida: {origem!r}.') from exc
