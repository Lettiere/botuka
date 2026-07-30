from django.db.models import Q
from apps.accounts.permissions import usuario_e_master,usuario_tem_permissao
from apps.organizations.permissions import empresas_gerenciaveis_para_usuario
from .models import Produto


def produtos_do_usuario(user):
    qs=Produto.objects.select_related('proprietario','responsavel','empresa_proprietaria')
    if usuario_e_master(user) or usuario_tem_permissao(user,'products.administrar_todos'): return qs
    companies=empresas_gerenciaveis_para_usuario(user).values_list('pk',flat=True)
    return qs.filter(Q(proprietario=user)|Q(responsavel=user)|Q(empresa_proprietaria_id__in=companies)).distinct()


def pode_editar(user,produto):
    if usuario_e_master(user) or usuario_tem_permissao(user,'products.administrar_todos'): return True
    if produto.empresa_proprietaria_id:
        return usuario_tem_permissao(user,'products.editar_empresa') and empresas_gerenciaveis_para_usuario(user).filter(pk=produto.empresa_proprietaria_id).exists()
    if produto.proprietario_id==user.id or produto.responsavel_id==user.id:
        return usuario_tem_permissao(user,'products.editar_proprios')
    return False
