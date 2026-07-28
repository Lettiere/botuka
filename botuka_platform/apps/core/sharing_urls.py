from django.urls import path

from . import sharing_views

app_name = 'sharing'

urlpatterns = [
    path('compartilhar/<slug:tipo>/<uuid:uuid>/', sharing_views.compartilhar, name='data'),
    path('qrcode/<slug:tipo>/<uuid:uuid>.png', sharing_views.qrcode_png, name='png'),
    path('qrcode/<slug:tipo>/<uuid:uuid>.svg', sharing_views.qrcode_svg, name='svg'),
    path('imprimir/<slug:tipo>/<uuid:uuid>/', sharing_views.imprimir, name='print'),
]
