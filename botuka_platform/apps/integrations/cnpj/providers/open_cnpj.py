from django.conf import settings

from apps.integrations.cnpj.exceptions import CNPJNotFoundError
from apps.integrations.cnpj.providers.base import BaseCNPJProvider
from apps.integrations.cnpj.providers.http import obter_json
from apps.integrations.cnpj.schemas import CNPJData


def _primeiro(payload, *nomes):
    for nome in nomes:
        if payload.get(nome) not in (None, ''):
            return payload[nome]
    return ''


def _cnaes(payload):
    itens = []
    principal = _primeiro(payload, 'cnae_fiscal', 'cnaePrincipal', 'cnae_principal')
    if isinstance(principal, dict):
        itens.append({**principal, 'principal': True})
    elif principal:
        itens.append({
            'codigo': principal,
            'descricao': _primeiro(
                payload, 'cnae_fiscal_descricao', 'descricaoCnaePrincipal',
                'cnae_principal_descricao',
            ),
            'principal': True,
        })
    secundarios = _primeiro(payload, 'cnaes_secundarios', 'cnaesSecundarios') or []
    itens.extend({**item, 'principal': False} for item in secundarios if isinstance(item, dict))
    return itens


class OpenCNPJProvider(BaseCNPJProvider):
    name = 'OpenCNPJ'
    base_url = 'https://api.opencnpj.org'

    def consultar(self, cnpj: str) -> CNPJData:
        base_url = getattr(settings, 'OPENCNPJ_BASE_URL', self.base_url).rstrip('/')
        timeout = int(getattr(settings, 'CNPJ_API_TIMEOUT', 10))
        payload = obter_json(f'{base_url}/{cnpj}', timeout=timeout)
        if payload.get('success') is False or ('data' in payload and payload.get('data') is None):
            raise CNPJNotFoundError('CNPJ não encontrado pelo OpenCNPJ.')
        # Algumas implantações envolvem o registro em ``data``.
        data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
        return CNPJData(
            cnpj=_primeiro(data, 'cnpj') or cnpj,
            razao_social=_primeiro(data, 'razao_social', 'razaoSocial'),
            nome_fantasia=_primeiro(data, 'nome_fantasia', 'nomeFantasia'),
            situacao_cadastral=_primeiro(
                data, 'descricao_situacao_cadastral', 'situacaoCadastral', 'situacao_cadastral',
            ),
            data_abertura=_primeiro(data, 'data_inicio_atividade', 'dataInicioAtividades'),
            natureza_juridica=_primeiro(data, 'natureza_juridica', 'naturezaJuridica'),
            porte=_primeiro(data, 'porte', 'descricao_porte'),
            telefone=_primeiro(data, 'ddd_telefone_1', 'telefone'),
            email=_primeiro(data, 'email'),
            logradouro=_primeiro(data, 'logradouro'), numero=_primeiro(data, 'numero'),
            complemento=_primeiro(data, 'complemento'), bairro=_primeiro(data, 'bairro'),
            municipio=_primeiro(data, 'municipio'), uf=_primeiro(data, 'uf'),
            cep=_primeiro(data, 'cep'), cnaes=_cnaes(data), raw={},
        )
