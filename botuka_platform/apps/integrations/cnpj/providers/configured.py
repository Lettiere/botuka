import json
import urllib.error
import urllib.request

from django.conf import settings

from apps.integrations.cnpj.exceptions import CNPJProviderError
from apps.integrations.cnpj.providers.base import BaseCNPJProvider
from apps.integrations.cnpj.schemas import CNPJData


class ConfiguredCNPJProvider(BaseCNPJProvider):
    name = 'configured'

    def consultar(self, cnpj: str) -> CNPJData:
        base_url = getattr(settings, 'CNPJ_API_BASE_URL', '')
        token = getattr(settings, 'CNPJ_API_TOKEN', '')
        timeout = int(getattr(settings, 'CNPJ_API_TIMEOUT', 10))

        if not base_url:
            raise CNPJProviderError('Provider de CNPJ não configurado.')

        request = urllib.request.Request(f'{base_url.rstrip("/")}/{cnpj}')
        if token:
            request.add_header('Authorization', f'Bearer {token}')

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise CNPJProviderError('Falha ao consultar provider de CNPJ.') from exc

        return CNPJData(
            cnpj=cnpj,
            razao_social=payload.get('razao_social') or payload.get('nome') or '',
            nome_fantasia=payload.get('nome_fantasia') or payload.get('fantasia') or '',
            situacao_cadastral=payload.get('situacao_cadastral') or payload.get('situacao') or '',
            data_abertura=payload.get('data_abertura') or payload.get('abertura') or '',
            natureza_juridica=payload.get('natureza_juridica') or '',
            porte=payload.get('porte') or '',
            telefone=payload.get('telefone') or '',
            email=payload.get('email') or '',
            logradouro=payload.get('logradouro') or '',
            numero=payload.get('numero') or '',
            complemento=payload.get('complemento') or '',
            bairro=payload.get('bairro') or '',
            municipio=payload.get('municipio') or payload.get('cidade') or '',
            uf=payload.get('uf') or '',
            cep=payload.get('cep') or '',
            cnaes=payload.get('cnaes') or [],
            raw=payload,
        )
