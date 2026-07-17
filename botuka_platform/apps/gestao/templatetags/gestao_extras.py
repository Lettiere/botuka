"""Filtros auxiliares para templates de gestão."""

from django import template

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

    tem_permissao = getattr(user, 'tem_permissao', None)
    return bool(callable(tem_permissao) and tem_permissao(code))
