from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .services.public_sharing import (
    gerar_material_impressao, gerar_qrcode_png, gerar_qrcode_svg,
    obter_dados_compartilhamento, obter_objeto_publico,
)


@require_GET
def compartilhar(request, tipo, uuid):
    obj = obter_objeto_publico(tipo, uuid)
    return JsonResponse(obter_dados_compartilhamento(obj, request))


@require_GET
def qrcode_png(request, tipo, uuid):
    obj = obter_objeto_publico(tipo, uuid)
    response = HttpResponse(gerar_qrcode_png(obj, request), content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="botuka-{tipo}-{uuid}.png"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@require_GET
def qrcode_svg(request, tipo, uuid):
    obj = obter_objeto_publico(tipo, uuid)
    response = HttpResponse(gerar_qrcode_svg(obj, request), content_type='image/svg+xml')
    response['Content-Disposition'] = f'inline; filename="botuka-{tipo}-{uuid}.svg"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@require_GET
def imprimir(request, tipo, uuid):
    obj = obter_objeto_publico(tipo, uuid)
    return render(request, 'publico/compartilhamento/impressao.html', {
        'objeto': obj, 'share': gerar_material_impressao(obj, request),
        'tipo_publico': tipo,
    })
