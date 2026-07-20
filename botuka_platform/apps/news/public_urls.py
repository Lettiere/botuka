from django.urls import path
from . import views
app_name='news_public';urlpatterns=[path('news/',views.home,name='home'),path('news/<slug:slug>/',views.categoria,name='categoria'),path('news/artigo/<slug:slug>/',views.artigo,name='artigo')]
