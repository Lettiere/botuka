from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """
    Exibe a página inicial pública do BOTUKA.
    """
    context = {
        "page": {
            "title": "BOTUKA",
            "section": "home",
        }
    }

    return render(request, "home/home.html", context)


def prestador_perfil(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Exibe o perfil público de um prestador de serviços.
    """
    context = {
        "page": {
            "title": "Perfil do Prestador",
            "section": "prestadores",
        },
        "prestador": {
            "nome": "Reformas Oliveira",
            "slug": slug,
        },
    }

    return render(
        request,
        "perfil_prestador/perfil_colaborador.html",
        context,
    )