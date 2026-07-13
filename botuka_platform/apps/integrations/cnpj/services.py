from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.integrations.cnpj.client import get_cnpj_provider
from apps.integrations.cnpj.exceptions import CNPJInvalidoError
from apps.organizations.models import CNPJConsulta, normalizar_digitos


def cnpj_valido(cnpj: str) -> bool:
    cnpj = normalizar_digitos(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos = ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    for indice, peso in enumerate(pesos):
        soma = sum(int(cnpj[i]) * peso[i] for i in range(len(peso)))
        digito = 11 - (soma % 11)
        digito = 0 if digito >= 10 else digito
        if digito != int(cnpj[12 + indice]):
            return False
    return True


def consultar_cnpj(cnpj, usuario=None):
    cnpj = normalizar_digitos(cnpj)
    if not cnpj_valido(cnpj):
        raise CNPJInvalidoError('CNPJ inválido.')

    provider = get_cnpj_provider()
    agora = timezone.now()
    cache = (
        CNPJConsulta.objects.filter(cnpj=cnpj, provider=provider.name, sucesso=True, expira_em__gt=agora)
        .order_by('-consultado_em')
        .first()
    )
    if cache:
        return cache.resposta_json

    cache_hours = int(getattr(settings, 'CNPJ_API_CACHE_HOURS', 24))
    try:
        dados = provider.consultar(cnpj)
        payload = dados.as_dict()
        CNPJConsulta.objects.create(
            cnpj=cnpj,
            provider=provider.name,
            sucesso=True,
            codigo_resposta='200',
            resposta_json=payload,
            expira_em=agora + timedelta(hours=cache_hours),
            solicitado_por=usuario if getattr(usuario, 'is_authenticated', False) else None,
        )
        return payload
    except Exception as exc:
        CNPJConsulta.objects.create(
            cnpj=cnpj,
            provider=provider.name,
            sucesso=False,
            erro_resumido=str(exc)[:240],
            solicitado_por=usuario if getattr(usuario, 'is_authenticated', False) else None,
        )
        raise
