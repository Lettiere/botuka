"""Regras centrais da taxonomia assistida."""

import re
import unicodedata

from django.db.models import Q
from django.core.exceptions import ValidationError
from django.db import models, transaction


def normalizar_nome_catalogo(nome):
    """Normaliza para comparação sem alterar o nome usado na exibição."""
    nome = re.sub(r'\s+', ' ', (nome or '').strip()).casefold()
    return ''.join(
        caractere
        for caractere in unicodedata.normalize('NFKD', nome)
        if not unicodedata.combining(caractere)
    )


def usuario_modera_taxonomia(usuario):
    return bool(
        usuario
        and getattr(usuario, 'is_authenticated', False)
        and (getattr(usuario, 'is_staff', False) or getattr(usuario, 'is_superuser', False))
    )


def filtro_visibilidade_catalogo(usuario=None, prefixo=''):
    campo = lambda nome: f'{prefixo}{nome}'
    filtro = Q(**{campo('status_catalogo'): 'APROVADO'})
    if usuario and getattr(usuario, 'is_authenticated', False):
        if usuario_modera_taxonomia(usuario):
            return filtro | Q(**{campo('status_catalogo'): 'PENDENTE'})
        return filtro | Q(
            **{
                campo('status_catalogo'): 'PENDENTE',
                campo('criado_por'): usuario,
            }
        )
    return filtro


def _nome_exibicao(nome):
    nome = re.sub(r'\s+', ' ', (nome or '').strip())
    if not nome:
        raise ValidationError('Informe o nome da sugestão.')
    if len(nome) > 120:
        raise ValidationError('O nome deve ter no máximo 120 caracteres.')
    return nome


def _item_reutilizavel(modelo, usuario, nome_normalizado, **escopo):
    return modelo.objects.filter(
        nome_normalizado=nome_normalizado,
        ativo=True,
    ).filter(
        Q(status_catalogo='APROVADO')
        | Q(status_catalogo='PENDENTE', criado_por=usuario)
    ).filter(**escopo).order_by(
        models.Case(
            models.When(status_catalogo='APROVADO', then=0),
            default=1,
        ),
        'pk',
    ).first()


def _sugerir_item(modelo, usuario, nome, **escopo):
    nome = _nome_exibicao(nome)
    nome_normalizado = normalizar_nome_catalogo(nome)
    existente = _item_reutilizavel(
        modelo, usuario, nome_normalizado, **escopo,
    )
    if existente:
        return existente, False
    return modelo.objects.create(
        nome=nome,
        origem='USUARIO',
        status_catalogo='PENDENTE',
        criado_por=usuario,
        **escopo,
    ), True


def _obter_visivel(modelo, usuario, pk, mensagem):
    if not str(pk or '').isdigit():
        raise ValidationError(mensagem)
    item = modelo.objects.visiveis_para(usuario).filter(pk=pk, ativo=True).first()
    if not item:
        raise ValidationError(mensagem)
    return item


@transaction.atomic
def sugerir_setor(usuario, nome):
    from apps.services.models import Setor
    return _sugerir_item(Setor, usuario, nome)


@transaction.atomic
def sugerir_area(usuario, nome, setor_id):
    from apps.services.models import AreaProfissional, Setor
    setor = _obter_visivel(Setor, usuario, setor_id, 'Selecione um setor válido.')
    return _sugerir_item(AreaProfissional, usuario, nome, setor=setor)


@transaction.atomic
def sugerir_profissao(usuario, nome, setor_id, area_id):
    from apps.services.models import AreaProfissional, Profissao, Setor
    setor = _obter_visivel(Setor, usuario, setor_id, 'Selecione um setor válido.')
    area = _obter_visivel(
        AreaProfissional, usuario, area_id, 'Selecione uma área profissional válida.',
    )
    if area.setor_id != setor.pk:
        raise ValidationError('A área profissional não pertence ao setor selecionado.')
    return _sugerir_item(Profissao, usuario, nome, setor=setor, area=area)


@transaction.atomic
def sugerir_tipo_servico(usuario, nome, profissao_id):
    from apps.services.models import Profissao, ProfissaoTipoServico, TipoServico
    profissao = _obter_visivel(
        Profissao, usuario, profissao_id, 'Selecione uma profissão válida.',
    )
    tipo, tipo_criado = _sugerir_item(TipoServico, usuario, nome)
    vinculo = ProfissaoTipoServico.objects.visiveis_para(usuario).filter(
        profissao=profissao, tipo_servico=tipo, ativo=True,
    ).first()
    vinculo_criado = False
    if not vinculo:
        vinculo = ProfissaoTipoServico.objects.create(
            profissao=profissao,
            tipo_servico=tipo,
            origem='USUARIO',
            status_catalogo='PENDENTE',
            criado_por=usuario,
        )
        vinculo_criado = True
    return tipo, tipo_criado, vinculo, vinculo_criado
