from django.urls import path

from . import views


app_name = "news_public"

urlpatterns = [
    path("noticias/", views.home, name="home"),
    path("noticias/categoria/<slug:slug>/", views.categoria, name="categoria"),
    path("noticias/tema/<slug:slug>/", views.tema, name="tema"),
    path("noticias/tag/<slug:slug>/", views.tag, name="tag"),
    path("noticias/colunistas/", views.colunistas, name="colunistas"),
    path("noticias/colunistas/<slug:slug>/", views.colunista, name="colunista"),
    path("noticias/colunas/<slug:slug>/", views.coluna, name="coluna"),
    path("noticias/series/<slug:slug>/", views.serie, name="serie"),
    path("noticias/comentarios/<uuid:uuid>/responder/", views.comentario_responder, name="comentario_responder"),
    path("noticias/comentarios/<uuid:uuid>/editar/", views.comentario_editar, name="comentario_editar"),
    path("noticias/comentarios/<uuid:uuid>/excluir/", views.comentario_excluir, name="comentario_excluir"),
    path("noticias/comentarios/<uuid:uuid>/curtir/", views.comentario_curtir, name="comentario_curtir"),
    path("noticias/comentarios/<uuid:uuid>/denunciar/", views.comentario_denunciar, name="comentario_denunciar"),
    path("noticias/comentarios/<uuid:uuid>/moderar/", views.comentario_moderar, name="comentario_moderar"),
    path("noticias/<slug:slug>/comentarios/novo/", views.comentario_novo, name="comentario_novo"),
    path("noticias/<slug:slug>/", views.artigo, name="artigo"),
    path("news/", views.legacy_home, name="legacy_home"),
    path("news/artigo/<slug:slug>/", views.artigo, name="legacy_artigo"),
    path("news/<slug:slug>/", views.categoria, name="legacy_categoria"),
]
