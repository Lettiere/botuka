"""Regras centrais da taxonomia assistida."""

import re
import unicodedata

from django.db.models import Q


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
