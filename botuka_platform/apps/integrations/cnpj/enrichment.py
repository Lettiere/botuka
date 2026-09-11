from dataclasses import dataclass, field

from apps.integrations.cnpj.providers.brasil_api import BrasilAPIProvider
from apps.integrations.cnpj.providers.open_cnpj import OpenCNPJProvider
from apps.integrations.cnpj.services import consultar_cnpj
from apps.organizations.models import normalizar_digitos


FIELD_MAP = {
    'razao_social': 'razao_social',
    'nome_fantasia': 'nome_fantasia',
    'situacao_cadastral': 'descricao_situacao_cadastral',
    'porte': 'porte',
    'natureza_juridica': 'natureza_juridica',
    'data_abertura': 'data_inicio_atividade',
    'cep': 'cep',
    'logradouro': 'logradouro',
    'numero': 'numero',
    'complemento': 'complemento',
    'bairro': 'bairro',
    'municipio': 'municipio',
    'uf': 'uf',
    'telefone': 'ddd_telefone_1',
    'email': 'email',
}


@dataclass
class ResultadoEnriquecimento:
    registro: dict
    fontes: list[str] = field(default_factory=list)
    fontes_por_campo: dict[str, str] = field(default_factory=dict)
    erros: list[str] = field(default_factory=list)

    @property
    def fonte_resumo(self):
        return ' / '.join(self.fontes) or 'nenhuma'


def _presente(valor) -> bool:
    return valor is not None and str(valor).strip() != ''


def _codigo_cnae(item) -> str:
    if not isinstance(item, dict):
        return normalizar_digitos(item)
    return normalizar_digitos(item.get('codigo') or item.get('cnae') or item.get('cnae_fiscal'))


def _faltam_dados(registro: dict) -> bool:
    if any(not _presente(registro.get(destino)) for destino in FIELD_MAP.values()):
        return True
    if not _presente(registro.get('cnae_fiscal')):
        return True
    if not _presente(registro.get('cnae_fiscal_descricao')):
        return True
    return False


def _complementar_cnaes(registro: dict, dados: dict, fonte: str, fontes: dict) -> None:
    cnaes = dados.get('cnaes') or []
    principal = next((item for item in cnaes if item.get('principal')), None)
    if not _presente(registro.get('cnae_fiscal')) and principal:
        registro['cnae_fiscal'] = _codigo_cnae(principal)
        registro['cnae_fiscal_descricao'] = principal.get('descricao') or ''
        fontes['cnae_principal'] = fonte
    elif (
        not _presente(registro.get('cnae_fiscal_descricao'))
        and principal
        and _codigo_cnae(principal) == normalizar_digitos(registro.get('cnae_fiscal'))
    ):
        registro['cnae_fiscal_descricao'] = principal.get('descricao') or ''
        if registro['cnae_fiscal_descricao']:
            fontes['cnae_principal_descricao'] = fonte

    secundarios = list(registro.get('cnaes_secundarios') or [])
    vistos = {normalizar_digitos(registro.get('cnae_fiscal'))}
    vistos.update(_codigo_cnae(item) for item in secundarios)
    adicionou = False
    for item in cnaes:
        codigo = _codigo_cnae(item)
        if not codigo or item.get('principal') or codigo in vistos:
            continue
        secundarios.append({'codigo': codigo, 'descricao': item.get('descricao') or ''})
        vistos.add(codigo)
        adicionou = True
    registro['cnaes_secundarios'] = secundarios
    if adicionou:
        fontes['cnaes_secundarios'] = fonte


def enriquecer_registro(registro: dict, *, providers=None) -> ResultadoEnriquecimento:
    """Complementa somente lacunas; nunca decide elegibilidade nem persiste dados."""
    enriquecido = dict(registro)
    enriquecido['cnaes_secundarios'] = list(registro.get('cnaes_secundarios') or [])
    resultado = ResultadoEnriquecimento(registro=enriquecido)
    providers = providers or (OpenCNPJProvider(), BrasilAPIProvider())

    for provider in providers:
        if not _faltam_dados(enriquecido):
            break
        try:
            dados = consultar_cnpj(
                enriquecido.get('cnpj'), provider=provider, persistir=False,
            )
        except Exception as exc:  # falha isolada: o lote deve continuar
            resultado.erros.append(f'{provider.name}: {str(exc)[:160]}')
            continue

        complementou = False
        for origem, destino in FIELD_MAP.items():
            if not _presente(enriquecido.get(destino)) and _presente(dados.get(origem)):
                enriquecido[destino] = dados[origem]
                resultado.fontes_por_campo[destino] = provider.name
                complementou = True
        antes = len(resultado.fontes_por_campo)
        _complementar_cnaes(enriquecido, dados, provider.name, resultado.fontes_por_campo)
        complementou = complementou or len(resultado.fontes_por_campo) > antes
        if complementou:
            resultado.fontes.append(provider.name)
    return resultado
