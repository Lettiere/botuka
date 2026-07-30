from django.urls import path
from . import views

app_name = 'products'
urlpatterns = [
    path('loja/', views.loja, name='loja'),
    path('produtos/<slug:slug>/', views.publico_detalhe, name='detalhe'),
]
