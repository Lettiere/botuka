from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.integrations.cnpj.services import cnpj_valido
from apps.integrations.cnpj.enrichment import enriquecer_registro
from apps.integrations.minha_receita import MinhaReceitaClient
from apps.locations.models import Cidade, Estado
from apps.organizations.models import CNAE, Empresa, EmpresaCNAE, normalizar_digitos


BOTUCATU_IBGE = '3507506'
MAXIMO_REGISTROS_POR_PAGINA = 1024


def normalizar_texto(valor) -> str:
    texto = unicodedata.normalize('NFKD', str(valor or '').strip())
    return ''.join(char for char in texto if not unicodedata.combining(char)).upper()


def _texto(valor, *chaves) -> str:
    if isinstance(valor, dict):
        for chave in chaves or ('descricao', 'nome'):
            if valor.get(chave):
                return str(valor[chave]).strip()
        return ''
    return str(valor or '').strip()


def _limitar(valor, tamanho: int) -> str:
    return str(valor or '').strip()[:tamanho]


def _data(valor):
    texto = str(valor or '').strip()
    for formato in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(texto[:10], formato).date()
        except ValueError:
            pass
    return None


def _endereco(registro: dict) -> str:
    logradouro = _texto(registro.get('logradouro'))
    tipo = _texto(registro.get('descricao_tipo_de_logradouro'))
    if tipo and logradouro and not normalizar_texto(logradouro).startswith(normalizar_texto(tipo)):
        return f'{tipo} {logradouro}'
    return logradouro


def _cnae(item, descricao='') -> tuple[str, str]:
    if isinstance(item, dict):
        codigo = item.get('codigo') or item.get('cnae') or item.get('cnae_fiscal')
        descricao = item.get('descricao') or item.get('descricao_atividade') or descricao
    else:
        codigo = item
    return normalizar_digitos(codigo), _texto(descricao)


def _cnaes(registro: dict) -> list[tuple[str, str, bool]]:
    encontrados = []
    vistos = set()
    codigo, descricao = _cnae(registro.get('cnae_fiscal'), registro.get('cnae_fiscal_descricao'))
    if codigo:
        encontrados.append((codigo, descricao, True))
        vistos.add(codigo)
    for item in registro.get('cnaes_secundarios') or []:
        codigo, descricao = _cnae(item)
        if codigo and codigo not in vistos:
            encontrados.append((codigo, descricao, False))
            vistos.add(codigo)
    return encontrados


def normalizar_registro_final(registro: dict) -> dict:
    """Materializa o único registro consumido pela revisão e pela persistência."""
    # Somente campos com uso na prévia/persistência atravessam a fronteira do
    # serviço. Isso evita carregar QSA, respostas brutas ou dados sem destino.
    campos_permitidos = {
        'cnpj', 'razao_social', 'nome_fantasia', 'natureza_juridica', 'porte',
        'data_inicio_atividade', 'descricao_situacao_cadastral', 'cep', 'uf',
        'municipio', 'codigo_municipio_ibge', 'logradouro',
        'descricao_tipo_de_logradouro', 'numero', 'complemento', 'bairro',
        'ddd_telefone_1', 'email', 'cnae_fiscal', 'cnae_fiscal_descricao',
        'cnaes_secundarios',
    }
    final = {chave: registro.get(chave) for chave in campos_permitidos}
    razao_social = _limitar(registro.get('razao_social'), 180)
    final.update({
        'cnpj': normalizar_digitos(registro.get('cnpj')),
        'razao_social': razao_social,
        'nome_fantasia': _limitar(registro.get('nome_fantasia') or razao_social, 180),
        'natureza_juridica': _limitar(_texto(registro.get('natureza_juridica')), 120),
        'porte': _limitar(_texto(registro.get('porte')), 40),
        'cep': normalizar_digitos(registro.get('cep'))[:8],
        'numero': _limitar(registro.get('numero'), 20),
        'complemento': _limitar(registro.get('complemento'), 120),
        'bairro': _limitar(registro.get('bairro'), 120),
        'ddd_telefone_1': normalizar_digitos(registro.get('ddd_telefone_1'))[:20],
        'email': _limitar(str(registro.get('email') or '').lower(), 254),
    })
    final['cnaes_secundarios'] = [
        {'codigo': codigo, 'descricao': descricao}
        for codigo, descricao, principal in _cnaes(registro) if not principal
    ]
    principal = next(
        ((codigo, descricao) for codigo, descricao, is_principal in _cnaes(registro)
         if is_principal),
        ('', ''),
    )
    final['cnae_fiscal'], final['cnae_fiscal_descricao'] = principal
    return final


def classificar_registro(registro: dict) -> tuple[str, str]:
    if not isinstance(registro, dict):
        return 'INVALIDA', 'Registro da fonte não é um objeto'
    cnpj = normalizar_digitos(registro.get('cnpj'))
    if not cnpj_valido(cnpj):
        return 'INVALIDA', 'CNPJ ausente ou inválido'
    if normalizar_texto(registro.get('uf')) != 'SP':
        return 'FORA_MUNICIPIO', 'UF diferente de SP'
    if normalizar_texto(registro.get('municipio')) != 'BOTUCATU':
        return 'FORA_MUNICIPIO', 'Município diferente de Botucatu'
    if normalizar_digitos(registro.get('codigo_municipio_ibge')) != BOTUCATU_IBGE:
        return 'FORA_MUNICIPIO', 'Código IBGE diferente de 3507506'
    if normalizar_texto(registro.get('descricao_situacao_cadastral')) != 'ATIVA':
        return 'INATIVA', 'Situação cadastral não ativa'
    return 'CANDIDATA', ''


@dataclass
class ItemDescoberta:
    cnpj: str
    nome: str
    bairro: str
    cnae_principal: str
    situacao: str
    resultado: str
    detalhe: str = ''
    empresa_id: int | None = None
    razao_social: str = ''
    nome_fantasia: str = ''
    porte: str = ''
    natureza_juridica: str = ''
    data_abertura: str = ''
    cep: str = ''
    endereco: str = ''
    numero: str = ''
    complemento: str = ''
    cidade: str = ''
    uf: str = ''
    telefone: str = ''
    email: str = ''
    cnae_principal_descricao: str = ''
    cnaes_secundarios: list[tuple[str, str]] = field(default_factory=list)
    fonte_descoberta: str = 'Minha Receita'
    fonte_enriquecimento: str = 'nenhuma'
    campos_enriquecidos: dict[str, str] = field(default_factory=dict)
    erros_enriquecimento: list[str] = field(default_factory=list)
    completude: str = 'INCOMPLETO'
    campos_ausentes_revisao: list[str] = field(default_factory=list)
    registro_final: dict = field(default_factory=dict, repr=False)


@dataclass
class ResultadoDescoberta:
    recebidas: int = 0
    ativas_validas: int = 0
    rejeitadas: int = 0
    ja_existentes: int = 0
    candidatas: int = 0
    importadas: int = 0
    proximo_cursor: str | None = None
    itens: list[ItemDescoberta] = field(default_factory=list)


def _localizacao_botucatu() -> tuple[Estado, Cidade]:
    estado = Estado.objects.filter(sigla__iexact='SP', ativo=True).first()
    if not estado:
        raise ValidationError('Estado SP não cadastrado na base geográfica.')
    cidade = Cidade.objects.filter(estado=estado, codigo_ibge=BOTUCATU_IBGE, ativo=True).first()
    if not cidade:
        cidade = Cidade.objects.filter(estado=estado, nome__iexact='Botucatu', ativo=True).first()
    if not cidade:
        raise ValidationError('Cidade de Botucatu não cadastrada na base geográfica.')
    return estado, cidade


@transaction.atomic
def importar_registro(registro: dict) -> tuple[Empresa, bool]:
    registro = normalizar_registro_final(registro)
    resultado, detalhe = classificar_registro(registro)
    if resultado != 'CANDIDATA':
        raise ValidationError(detalhe)

    cnpj = normalizar_digitos(registro['cnpj'])
    existente = Empresa.all_objects.filter(cpf_cnpj=cnpj, excluido_em__isnull=True).first()
    if existente:
        return existente, False

    estado, cidade = _localizacao_botucatu()
    telefone_1 = normalizar_digitos(registro.get('ddd_telefone_1'))
    razao_social = _limitar(registro.get('razao_social'), 180)
    empresa = Empresa.objects.create(
        usuario_proprietario=None,
        criado_por=None,
        tipo_cadastro=Empresa.TipoCadastro.EMPRESA,
        origem_cadastro=Empresa.OrigemCadastro.API,
        razao_social=razao_social,
        nome_fantasia=_limitar(registro.get('nome_fantasia') or razao_social, 180),
        cpf_cnpj=cnpj,
        natureza_juridica=_limitar(_texto(registro.get('natureza_juridica')), 120),
        porte=_limitar(_texto(registro.get('porte')), 40),
        data_abertura=_data(registro.get('data_inicio_atividade')),
        situacao_cadastral=_limitar(registro.get('descricao_situacao_cadastral'), 60),
        cep=normalizar_digitos(registro.get('cep'))[:8],
        endereco=_limitar(_endereco(registro), 180),
        numero=_limitar(registro.get('numero'), 20),
        complemento=_limitar(registro.get('complemento'), 120),
        bairro=_limitar(registro.get('bairro'), 120),
        estado=estado,
        cidade=cidade,
        telefone=telefone_1[:20],
        email=_limitar(str(registro.get('email') or '').lower(), 254),
        status=Empresa.Status.ATIVA,
        perfil_publico=True,
        ativo=True,
    )
    _sincronizar_cnaes(empresa, registro)
    return empresa, True


def _sincronizar_cnaes(empresa: Empresa, registro: dict) -> None:
    recebidos = _cnaes(registro)
    codigos = {codigo for codigo, _, _ in recebidos}
    EmpresaCNAE.objects.filter(
        empresa=empresa, origem=EmpresaCNAE.Origem.RECEITA, ativo=True,
    ).exclude(cnae__codigo__in=codigos).update(ativo=False, principal=False)

    principal = next((codigo for codigo, _, is_principal in recebidos if is_principal), None)
    if principal:
        EmpresaCNAE.objects.filter(empresa=empresa, principal=True, ativo=True).exclude(
            cnae__codigo=principal,
        ).update(principal=False)

    for codigo, descricao, is_principal in recebidos:
        cnae, _ = CNAE.objects.get_or_create(
            codigo=codigo,
            defaults={'descricao': descricao or 'Descrição não informada pela fonte'},
        )
        EmpresaCNAE.objects.update_or_create(
            empresa=empresa,
            cnae=cnae,
            defaults={
                'principal': is_principal,
                'origem': EmpresaCNAE.Origem.RECEITA,
                'ativo': True,
            },
        )


def avaliar_completude(registro: dict) -> tuple[str, list[str]]:
    """Heurística não bloqueante para a fila de revisão (não é regra de importação)."""
    requisitos = {
        'CNPJ': normalizar_digitos(registro.get('cnpj')),
        'nome/razão social': registro.get('nome_fantasia') or registro.get('razao_social'),
        'CEP': registro.get('cep'),
        'logradouro': _endereco(registro),
        'bairro': registro.get('bairro'),
        'cidade': registro.get('municipio'),
        'UF': registro.get('uf'),
        'CNAE principal': normalizar_digitos(registro.get('cnae_fiscal')),
    }
    ausentes = [rotulo for rotulo, valor in requisitos.items() if not _texto(valor)]
    if not ausentes:
        return 'COMPLETO', []
    if requisitos['CNPJ'] and requisitos['nome/razão social']:
        return 'PARCIAL', ausentes
    return 'INCOMPLETO', ausentes


def discover_batch(
    *, limit=100, cursor=None, dry_run=True, client=None, enriquecer=False,
    enrichment_providers=None,
) -> ResultadoDescoberta:
    if not 1 <= int(limit) <= MAXIMO_REGISTROS_POR_PAGINA:
        raise ValueError(f'limit deve estar entre 1 e {MAXIMO_REGISTROS_POR_PAGINA}.')
    payload = (client or MinhaReceitaClient()).discover_batch(limit=int(limit), cursor=cursor)
    resultado = ResultadoDescoberta(
        recebidas=len(payload['data']), proximo_cursor=payload.get('cursor')
    )
    for registro in payload['data']:
        status, detalhe = classificar_registro(registro)
        registro = registro if isinstance(registro, dict) else {}
        cnpj = normalizar_digitos(registro.get('cnpj'))
        empresa = None
        criada = False
        enriquecimento = None
        if status == 'CANDIDATA':
            resultado.ativas_validas += 1
            existente = Empresa.all_objects.filter(cpf_cnpj=cnpj, excluido_em__isnull=True).first()
            if existente:
                status, detalhe = 'JA_EXISTE', 'CNPJ já cadastrado; nenhum dado foi sobrescrito'
                resultado.ja_existentes += 1
            else:
                resultado.candidatas += 1
                if enriquecer:
                    enriquecimento = enriquecer_registro(
                        registro, providers=enrichment_providers,
                    )
                    registro = enriquecimento.registro
                registro = normalizar_registro_final(registro)
                if not dry_run:
                    try:
                        empresa, criada = importar_registro(registro)
                    except Exception as exc:
                        # Cada importação abre seu próprio savepoint atômico. Um
                        # registro defeituoso não pode abortar os demais da página.
                        status = 'ERRO'
                        detalhe = f'Falha isolada ao importar registro: {exc}'
                        resultado.rejeitadas += 1
                    else:
                        if criada:
                            resultado.importadas += 1
        else:
            resultado.rejeitadas += 1
        cnaes = _cnaes(registro)
        completude, ausentes = avaliar_completude(registro)
        cnae_principal = next(
            ((codigo, descricao) for codigo, descricao, principal in cnaes if principal),
            ('', ''),
        )
        resultado.itens.append(ItemDescoberta(
            cnpj=cnpj,
            nome=_texto(registro.get('nome_fantasia') or registro.get('razao_social')),
            bairro=_texto(registro.get('bairro')),
            cnae_principal=cnae_principal[0],
            situacao=_texto(registro.get('descricao_situacao_cadastral')),
            resultado=status,
            detalhe=detalhe,
            empresa_id=empresa.pk if empresa is not None and criada else None,
            razao_social=_texto(registro.get('razao_social')),
            nome_fantasia=_texto(registro.get('nome_fantasia')),
            porte=_texto(registro.get('porte')),
            natureza_juridica=_texto(registro.get('natureza_juridica')),
            data_abertura=_texto(registro.get('data_inicio_atividade')),
            cep=_texto(registro.get('cep')),
            endereco=_endereco(registro),
            numero=_texto(registro.get('numero')),
            complemento=_texto(registro.get('complemento')),
            cidade=_texto(registro.get('municipio')),
            uf=_texto(registro.get('uf')),
            telefone=_texto(registro.get('ddd_telefone_1')),
            email=_texto(registro.get('email')),
            cnae_principal_descricao=cnae_principal[1],
            cnaes_secundarios=[
                (codigo, descricao) for codigo, descricao, principal in cnaes if not principal
            ],
            fonte_enriquecimento=(
                enriquecimento.fonte_resumo if enriquecimento is not None else 'nenhuma'
            ),
            campos_enriquecidos=(
                enriquecimento.fontes_por_campo if enriquecimento is not None else {}
            ),
            erros_enriquecimento=(
                enriquecimento.erros if enriquecimento is not None else []
            ),
            completude=completude,
            campos_ausentes_revisao=ausentes,
            registro_final=registro,
        ))
    return resultado
