"""Views internas do módulo Comunicação BOTUKA."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.gestao.decorators import master_required

from .models import (
    CampanhaDestinatario,
    CampanhaEmail,
    Distribuicao,
    DistribuicaoDestinatario,
    InteracaoProspeccao,
    ListaProspeccao,
    ProspectoContato,
    ProspectoEmpresa,
    SupressaoEmail,
    TemplateEmail,
)


def _ativos(model):
    return model.objects.filter(
        ativo=True,
        removido_em__isnull=True,
    )


@master_required
def dashboard(request: HttpRequest) -> HttpResponse:
    context = {
        "section": "Comunicação",
        "prospectos": _ativos(ProspectoEmpresa).count(),
        "contatos": _ativos(ProspectoContato).count(),
        "listas_prospeccao": _ativos(ListaProspeccao).count(),
        "interacoes": _ativos(InteracaoProspeccao).count(),
        "distribuicoes": _ativos(Distribuicao).count(),
        "destinatarios_distribuicao": _ativos(
            DistribuicaoDestinatario
        ).count(),
        "campanhas": _ativos(CampanhaEmail).count(),
        "destinatarios_campanha": _ativos(
            CampanhaDestinatario
        ).count(),
        "templates_email": _ativos(TemplateEmail).count(),
        "supressoes": _ativos(SupressaoEmail).count(),
    }

    return render(
        request,
        "gestao/comunicacao/dashboard.html",
        context,
    )


@master_required
def prospeccao(request: HttpRequest) -> HttpResponse:
    prospectos = _ativos(ProspectoEmpresa)

    context = {
        "section": "Comunicação · Prospecção",
        "total": prospectos.count(),
        "novos": prospectos.filter(
            status=ProspectoEmpresa.Status.NOVO
        ).count(),
        "contatados": prospectos.filter(
            status=ProspectoEmpresa.Status.CONTATADO
        ).count(),
        "interessados": prospectos.filter(
            status=ProspectoEmpresa.Status.INTERESSADO
        ).count(),
        "negociacao": prospectos.filter(
            status=ProspectoEmpresa.Status.NEGOCIACAO
        ).count(),
        "convertidos": prospectos.filter(
            status=ProspectoEmpresa.Status.CONVERTIDO
        ).count(),
        "nao_contatar": prospectos.filter(
            status=ProspectoEmpresa.Status.NAO_CONTATAR
        ).count(),
        "contatos": _ativos(ProspectoContato).count(),
        "listas": _ativos(ListaProspeccao).count(),
        "interacoes": _ativos(InteracaoProspeccao).count(),
    }

    return render(
        request,
        "gestao/comunicacao/prospeccao/index.html",
        context,
    )


@master_required
def distribuicao(request: HttpRequest) -> HttpResponse:
    context = {
        "section": "Comunicação · Distribuição",
        "distribuicoes": _ativos(Distribuicao).count(),
        "destinatarios": _ativos(
            DistribuicaoDestinatario
        ).count(),
        "supressoes": _ativos(SupressaoEmail).count(),
    }

    return render(
        request,
        "gestao/comunicacao/distribuicao/index.html",
        context,
    )


@master_required
def marketing(request: HttpRequest) -> HttpResponse:
    context = {
        "section": "Comunicação · E-mail Marketing",
        "campanhas": _ativos(CampanhaEmail).count(),
        "destinatarios": _ativos(
            CampanhaDestinatario
        ).count(),
        "templates": _ativos(TemplateEmail).count(),
        "supressoes": _ativos(SupressaoEmail).count(),
    }

    return render(
        request,
        "gestao/comunicacao/marketing/index.html",
        context,
    )
