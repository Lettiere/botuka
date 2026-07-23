"""Filtros auxiliares para templates de gestão."""

from django import template
from apps.accounts.permissions import usuario_tem_permissao

register = template.Library()


@register.filter
def attr(obj: object, name: str) -> object:
    """Obtém atributo ou método sem argumentos de um objeto."""

    if name == '__str__':
        return str(obj)

    value = obj
    for part in name.split('.'):
        value = getattr(value, part, '')
        if callable(value):
            value = value()

    return value



@register.filter
def has_perm_code(user: object, code: str) -> bool:
    """Permite checar permissão de domínio em templates."""

    return usuario_tem_permissao(user, code)
