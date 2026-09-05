"""Resolução do contexto empresarial selecionado no painel."""

from django.core.exceptions import PermissionDenied

from apps.organizations.permissions import empresas_disponiveis_para_usuario


SESSION_KEY = 'painel_empresa_selecionada_id'


def selecionar_empresa(request, empresa):
    """Persiste uma empresa já autorizada como contexto atual do painel."""
    request.session[SESSION_KEY] = empresa.pk
    return empresa


def limpar_empresa_selecionada(request):
    """Remove da sessão o contexto empresarial atual do painel."""
    request.session.pop(SESSION_KEY, None)


def empresa_selecionada(request):
    """Retorna a empresa acessível indicada na URL ou guardada na sessão.

    O parâmetro explícito troca o contexto apenas depois da validação de acesso.
    Contextos revogados ou inexistentes são descartados da sessão.
    """
    empresa_id = request.GET.get('empresa')
    if empresa_id is not None:
        empresa_id = empresa_id.strip()
        if not empresa_id.isdigit():
            raise PermissionDenied
        empresa = empresas_disponiveis_para_usuario(request.user).filter(
            pk=empresa_id,
        ).first()
        if empresa is None:
            raise PermissionDenied
        return selecionar_empresa(request, empresa)

    empresa_id = request.session.get(SESSION_KEY)
    if not empresa_id:
        return None
    empresa = empresas_disponiveis_para_usuario(request.user).filter(
        pk=empresa_id,
    ).first()
    if empresa is None:
        limpar_empresa_selecionada(request)
        return None
    return empresa
