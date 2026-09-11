from django.conf import settings

from apps.integrations.cnpj.providers.base import BaseCNPJProvider
from apps.integrations.cnpj.providers.http import obter_json
from apps.integrations.cnpj.schemas import CNPJData


def _cnaes(payload):
    itens = []
    if payload.get('cnae_fiscal'):
        itens.append({
            'codigo': payload['cnae_fiscal'],
            'descricao': payload.get('cnae_fiscal_descricao') or '',
            'principal': True,
        })
    itens.extend({**item, 'principal': False} for item in payload.get('cnaes_secundarios') or [])
    return itens


class BrasilAPIProvider(BaseCNPJProvider):
    name = 'BrasilAPI'
    base_url = 'https://brasilapi.com.br/api/cnpj/v1'

    def consultar(self, cnpj: str) -> CNPJData:
        base_url = getattr(settings, 'BRASIL_API_CNPJ_BASE_URL', self.base_url).rstrip('/')
        timeout = int(getattr(settings, 'CNPJ_API_TIMEOUT', 10))
        payload = obter_json(f'{base_url}/{cnpj}', timeout=timeout)
        return CNPJData(
            cnpj=payload.get('cnpj') or cnpj,
            razao_social=payload.get('razao_social') or '',
            nome_fantasia=payload.get('nome_fantasia') or '',
            situacao_cadastral=payload.get('descricao_situacao_cadastral') or '',
            data_abertura=payload.get('data_inicio_atividade') or '',
            natureza_juridica=payload.get('natureza_juridica') or '',
            porte=payload.get('porte') or payload.get('descricao_porte') or '',
            telefone=payload.get('ddd_telefone_1') or '',
            email=payload.get('email') or '',
            logradouro=payload.get('logradouro') or '', numero=payload.get('numero') or '',
            complemento=payload.get('complemento') or '', bairro=payload.get('bairro') or '',
            municipio=payload.get('municipio') or '', uf=payload.get('uf') or '',
            cep=payload.get('cep') or '', cnaes=_cnaes(payload), raw={},
        )
