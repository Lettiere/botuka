from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao
from apps.government.models import AcaoPublica
from apps.news.models import Artigo
from apps.organizations.models import Assinatura, Empresa
from apps.organizations.permissions import empresas_disponiveis_para_usuario, usuario_pode_publicar_por_empresa
from apps.organizations.plans import LimiteUsuarioService, usuario_pode_criar_empresa, usuario_pode_criar_servico
from apps.recruitment.models import Candidatura, Curriculo, Vaga
from apps.services.models import Servico
from apps.services.permissions import servicos_disponiveis_para_usuario
from apps.sports.models import OrganizacaoEsportiva


def _can(user, *codes):
    return usuario_e_master(user) or any(usuario_tem_permissao(user, code) for code in codes)


def _assinatura_atual(usuario):
    agora = timezone.now()
    return (Assinatura.objects.select_related("plano")
        .filter(usuario=usuario, ativo=True, excluido_em__isnull=True, status=Assinatura.Status.ATIVA, inicio__lte=agora)
        .filter(Q(fim__isnull=True) | Q(fim__gt=agora)).order_by("-inicio").first())


def _percentual_curriculo(curriculo):
    if not curriculo:
        return 0
    values = [curriculo.titulo_profissional, curriculo.resumo, curriculo.cidade, curriculo.estado, curriculo.linkedin or curriculo.portfolio]
    return round(sum(bool(value) for value in values) / len(values) * 100)


def montar_dashboard_conta(usuario):
    empresas_qs = empresas_disponiveis_para_usuario(usuario).annotate(
        qtd_servicos=Count("servicos", filter=Q(servicos__ativo=True, servicos__excluido_em__isnull=True), distinct=True),
        qtd_vagas=Count("vagas", filter=Q(vagas__ativo=True, vagas__excluido_em__isnull=True), distinct=True),
        qtd_colaboradores=Count("usuarios_vinculados", filter=Q(usuarios_vinculados__ativo=True), distinct=True),
    ).order_by("nome_fantasia")
    empresas = list(empresas_qs[:6])
    empresa_ids = list(empresas_qs.values_list("id", flat=True))
    empresas_proprias_ids = list(Empresa.objects.filter(usuario_proprietario=usuario).values_list("id", flat=True))

    servicos_qs = servicos_disponiveis_para_usuario(usuario)
    total_servicos = servicos_qs.count()
    servicos_ativos = servicos_qs.filter(status=Servico.Status.PUBLICADO).count()
    servicos_pausados = servicos_qs.filter(status=Servico.Status.PAUSADO).count()

    vagas_qs = Vaga.objects.filter(empresa_id__in=empresa_ids)
    vagas_total = vagas_qs.count()
    vagas_ativas = vagas_qs.filter(status=Vaga.Status.PUBLICADA).count()
    vagas_rascunho = vagas_qs.filter(status=Vaga.Status.RASCUNHO).count()
    vagas_encerradas = vagas_qs.filter(status=Vaga.Status.ENCERRADA).count()
    candidaturas_recebidas = Candidatura.objects.filter(vaga__empresa_id__in=empresa_ids).count()

    candidaturas = Candidatura.objects.filter(usuario=usuario).select_related("vaga", "vaga__empresa")
    candidaturas_total = candidaturas.count()
    curriculo = Curriculo.objects.filter(usuario=usuario).first()
    assinatura = _assinatura_atual(usuario)
    limite_empresa = usuario_pode_criar_empresa(usuario)
    limite_servico = usuario_pode_criar_servico(usuario)
    limites_efetivos = LimiteUsuarioService.obter_limites(usuario)

    publicacoes = {
        "cultura": Artigo.objects.filter(autor=usuario, ativo=True, excluido_em__isnull=True).count(),
        "esportes": OrganizacaoEsportiva.objects.filter(usuario_responsavel=usuario, ativo=True, excluido_em__isnull=True).count(),
        "oficiais": AcaoPublica.objects.filter(autor=usuario, ativo=True, excluido_em__isnull=True).count(),
    }
    pode_publicar_conteudo = _can(usuario, "eventos.criar", "news.criar", "sports.criar", "government.criar")
    pode_publicar_vaga = bool(empresas_proprias_ids) or any(usuario_pode_publicar_por_empresa(usuario, empresa) for empresa in empresas)

    actions = []
    if limite_empresa.permitido:
        actions.append({"title": "Cadastrar empresa", "description": "Apresente seu negócio, serviços e oportunidades para a cidade.", "url": reverse("painel:empresa_criar"), "icon": "bi-buildings"})
    if not curriculo:
        actions.append({"title": "Criar currículo", "description": "Organize sua experiência e candidate-se às vagas.", "url": reverse("painel:curriculo_novo"), "icon": "bi-file-earmark-person"})
    if limite_servico.permitido:
        actions.append({"title": "Cadastrar serviço", "description": "Ofereça um serviço como pessoa física ou por empresa autorizada.", "url": reverse("painel:servico_criar"), "icon": "bi-tools"})
    if pode_publicar_vaga and not vagas_total:
        actions.append({"title": "Publicar vaga", "description": "Encontre profissionais para sua empresa.", "url": reverse("painel:vaga_criar"), "icon": "bi-briefcase"})
    if pode_publicar_conteudo and not any(publicacoes.values()):
        actions.append({"title": "Criar publicação", "description": "Publique conteúdo nos módulos que você administra.", "url": reverse("painel:publicacoes_lista"), "icon": "bi-megaphone"})

    indicators = []
    if empresas: indicators.append({"label": "Empresas", "value": len(empresas), "icon": "bi-buildings"})
    if servicos_ativos: indicators.append({"label": "Serviços ativos", "value": servicos_ativos, "icon": "bi-tools"})
    if vagas_ativas: indicators.append({"label": "Vagas ativas", "value": vagas_ativas, "icon": "bi-briefcase"})
    if candidaturas_recebidas: indicators.append({"label": "Candidaturas recebidas", "value": candidaturas_recebidas, "icon": "bi-people"})
    if not empresas and not servicos_ativos and curriculo: indicators.append({"label": "Currículo preenchido", "value": f"{_percentual_curriculo(curriculo)}%", "icon": "bi-file-earmark-person"})
    if candidaturas_total and len(indicators) < 4: indicators.append({"label": "Minhas candidaturas", "value": candidaturas_total, "icon": "bi-person-check"})

    return {
        "is_initial": not empresas and not curriculo and not total_servicos,
        "indicators": indicators[:4], "actions": actions,
        "companies": empresas,
        "curriculum": {"object": curriculo, "completion": _percentual_curriculo(curriculo), "applications": candidaturas_total} if curriculo else None,
        "services": {"total": total_servicos, "active": servicos_ativos, "paused": servicos_pausados, "limit": limite_servico.limite, "can_create": limite_servico.permitido} if total_servicos else None,
        "jobs": {"total": vagas_total, "active": vagas_ativas, "draft": vagas_rascunho, "closed": vagas_encerradas, "applications": candidaturas_recebidas} if vagas_total else None,
        "applications": {"total": candidaturas_total} if candidaturas_total else None,
        "publications": publicacoes if any(publicacoes.values()) or pode_publicar_conteudo else None,
        "plan": {"name": assinatura.plano.nome if assinatura else "Gratuito", "valid_until": assinatura.fim if assinatura else None,
                 "companies_used": limite_empresa.total, "companies_limit": limite_empresa.limite, "can_create_company": limite_empresa.permitido,
                 "companies_remaining": limite_empresa.restante,
                 "services_used": limite_servico.total, "services_limit": limite_servico.limite,
                 "services_remaining": limite_servico.restante,
                 "personalized": limites_efetivos.personalizado},
    }
