from django.urls import path

from . import views

app_name = 'social_legacy'

urlpatterns = [
    path('social/', views.redirect_to_social, name='home'),
    path('social/<path:remainder>', views.redirect_to_social, name='path'),
    path('@<slug:slug>/', views.redirect_legacy_profile, name='profile'),
    path('painel/seguindo/', views.redirect_legacy_following, name='following'),
]
