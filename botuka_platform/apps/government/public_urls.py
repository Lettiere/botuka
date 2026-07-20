from django.urls import path
from . import views
app_name='government_public';urlpatterns=[path('prefeitura/',views.home,name='home'),path('prefeitura/orgaos/<slug:slug>/',views.orgao,name='orgao'),path('prefeitura/acoes/',views.acoes,name='acoes'),path('prefeitura/acoes/<slug:slug>/',views.acao,name='acao')]
