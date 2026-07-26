from django.core.exceptions import PermissionDenied

from apps.accounts.permissions import usuario_tem_permissao


def require(user, code):
    if not usuario_tem_permissao(user, code):
        raise PermissionDenied('Permissão insuficiente para esta ação.')


def pode_editar(user, obj, own_code, all_code):
    return (
        usuario_tem_permissao(user, all_code)
        or (
            obj.usuario_criador_id == user.pk
            and usuario_tem_permissao(user, own_code)
        )
    )


def objetos_editaveis(user, queryset, own_code, all_code):
    if usuario_tem_permissao(user, all_code):
        return queryset
    if usuario_tem_permissao(user, own_code):
        return queryset.filter(usuario_criador=user)
    return queryset.none()
