from django.urls import path
from django.views.generic import RedirectView

from . import views


urlpatterns = [
    path("noticias/", views.painel_dashboard, name="news_dashboard"),
    path("noticias/artigos/", views.artigo_lista, name="news_artigo_lista"),
    path("noticias/artigos/nova/", views.artigo_form, name="news_artigo_novo"),
    path("noticias/artigos/<uuid:uuid>/editar/", views.artigo_form, name="news_artigo_editar"),
    path("noticias/artigos/<uuid:uuid>/status/<str:status>/", views.artigo_status, name="news_artigo_status"),
    path("noticias/artigos/<uuid:uuid>/excluir/", views.artigo_excluir, name="news_artigo_excluir"),
    path("noticias/artigos/<uuid:uuid>/restaurar/", views.artigo_restaurar, name="news_artigo_restaurar"),
    path("noticias/revisoes/", views.artigo_lista, {"status": "ENVIADO_REVISAO"}, name="news_revisao"),
    path("noticias/agendamentos/", views.artigo_lista, {"status": "AGENDADO"}, name="news_agendamentos"),
    path("noticias/publicacoes/", views.artigo_lista, {"status": "PUBLICADO"}, name="news_publicacoes"),
    path("noticias/excluidos/", views.excluidos, name="news_excluidos"),
    path("noticias/configuracoes/", views.configuracoes, name="news_configuracoes"),
    path("noticias/cadastros/<slug:tipo>/", views.auxiliar_lista, name="news_auxiliar_lista"),
    path("noticias/cadastros/<slug:tipo>/novo/", views.auxiliar_form, name="news_auxiliar_novo"),
    path("noticias/cadastros/<slug:tipo>/<uuid:uuid>/editar/", views.auxiliar_form, name="news_auxiliar_editar"),

    # Aliases anteriores mantidos sem remover contratos existentes.
    path("news/", RedirectView.as_view(pattern_name="painel:news_dashboard", permanent=False), name="news_legacy_dashboard"),
    path("news/artigos/", views.artigo_lista, name="news_legacy_artigo_lista"),
    path("news/artigos/novo/", views.artigo_form, name="news_legacy_artigo_novo"),
    path("news/artigos/<uuid:uuid>/editar/", views.artigo_form, name="news_legacy_artigo_editar"),
    path("news/categorias/", views.categoria_lista, name="news_categorianoticia_lista"),
    path("news/categorias/novo/", views.categoria_novo, name="news_categorianoticia_novo"),
    path("news/categorias/<uuid:uuid>/editar/", views.categoria_editar, name="news_categorianoticia_editar"),
    path("news/fontes/", views.fonte_lista, name="news_artigofonte_lista"),
    path("news/fontes/novo/", views.fonte_novo, name="news_artigofonte_novo"),
    path("news/fontes/<uuid:uuid>/editar/", views.fonte_editar, name="news_artigofonte_editar"),
    path("news/blocos/", views.bloco_lista, name="news_artigobloco_lista"),
    path("news/blocos/novo/", views.bloco_novo, name="news_artigobloco_novo"),
    path("news/blocos/<uuid:uuid>/editar/", views.bloco_editar, name="news_artigobloco_editar"),
]
