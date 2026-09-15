from django import template

from apps.advertising.services import entregar_para_request

register = template.Library()

POSITION_CODES = {
    'leaderboard': 'public-leaderboard',
    'in-content': 'public-in-content',
    'sidebar': 'public-sidebar',
}


@register.inclusion_tag('advertising/components/ad.html', takes_context=True)
def advertising_slot(context, format='leaderboard', position_code='', page_context=''):
    request = context.get('request')
    if request is None or request.path.startswith(('/painel/', '/admin/', '/gestao/')):
        return {'entrega': None}
    empresa = context.get('empresa')
    categoria = context.get('categoria') or getattr(empresa, 'categoria_empresa', None)
    subcategoria = context.get('subcategoria') or getattr(empresa, 'subcategoria_empresa', None)
    cnae = context.get('cnae')
    if cnae is None and empresa is not None:
        vinculo_cnae = empresa.cnaes.select_related('cnae').order_by('-principal', 'pk').first()
        cnae = vinculo_cnae.cnae if vinculo_cnae else None
    resolver = getattr(request, 'resolver_match', None)
    entrega = entregar_para_request(
        request,
        posicionamento_codigo=position_code or POSITION_CODES.get(format, format),
        contexto=page_context or (resolver.view_name if resolver else request.path),
        categoria=categoria, subcategoria=subcategoria, cnae=cnae,
        termo=context.get('termo') or context.get('query', ''),
    )
    return {'entrega': entrega, 'format': format}
