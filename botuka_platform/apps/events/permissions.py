from django.db.models import Q

from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao
from apps.organizations.permissions import empresas_gerenciaveis_para_usuario

from .models import Evento


def empresas_para_eventos(user):
    if not usuario_tem_permissao(user, 'events.criar_empresa') and not usuario_e_master(user):
        return empresas_gerenciaveis_para_usuario(user).none()
    return empresas_gerenciaveis_para_usuario(user)


def eventos_do_usuario(user):
    qs = Evento.all_objects.select_related('empresa_promotora', 'proprietario', 'responsavel_edicao')
    if usuario_e_master(user) or usuario_tem_permissao(user, 'events.moderar'):
        return qs
    company_ids = empresas_para_eventos(user).values_list('pk', flat=True)
    return qs.filter(
        Q(proprietario=user) | Q(responsavel_edicao=user) | Q(empresa_promotora_id__in=company_ids)
    ).distinct()


def pode_editar_evento(user, evento):
    if usuario_e_master(user) or usuario_tem_permissao(user, 'events.editar_todos'):
        return True
    if evento.proprietario_id == user.id or evento.responsavel_edicao_id == user.id:
        return usuario_tem_permissao(user, 'events.editar_proprios')
    return bool(evento.empresa_promotora_id and usuario_tem_permissao(user, 'events.editar_empresa')
                and empresas_para_eventos(user).filter(pk=evento.empresa_promotora_id).exists())
