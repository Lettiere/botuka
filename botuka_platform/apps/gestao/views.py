"""Views do painel interno de gestão."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Exists, Model, OuterRef, Prefetch, Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from apps.core.models import ConfiguracaoSistema, ContatoInstitucional, Perfil, PerfilPermissao, Permissao
from apps.gestao.decorators import (
    DomainPermissionRequiredMixin,
    master_required,
    permission_required,
    staff_required,
)
from apps.accounts.authorization import criar_verificador_permissoes, pode
from apps.accounts.permissions import usuario_e_master
from apps.accounts.models import AcessoModulo, AuditoriaPermissao, ConcessaoPermissao
from apps.accounts.permission_services import (
    alterar_status_acesso, pode_administrar_permissoes,
    salvar_acesso_modulo,
)
from apps.organizations.services.institutional import atribuir_papel_global, revogar_papel_global
from apps.gestao.forms import (
    BairroForm,
    CategoriaForm,
    CidadeForm,
    ConfiguracaoSistemaForm,
    ContatoInstitucionalForm,
    EnderecoForm,
    EstadoForm,
    OrganizacaoForm,
    PaisForm,
    PerfilForm,
    PermissaoForm,
    SubcategoriaForm,
    UnidadeForm,
    AcessoModuloForm,
    UsuarioCreateForm,
    UsuarioForm,
)


MODULE_LABELS = {
    'news': 'Notícias', 'media': 'YoBotuka', 'events': 'Eventos',
    'sports': 'Esportes', 'tourism': 'Turismo', 'services': 'Serviços',
    'organizations': 'Empresas', 'recruitment': 'Recrutamento',
    'government': 'Governo', 'gestao': 'Gestão',
}


@staff_required
def usuario_acessos(request, uuid):
    if not pode_administrar_permissoes(request.user):
        raise PermissionDenied
    usuario = get_object_or_404(get_user_model(), uuid=uuid)
    can_modify_target = (
        request.user.pk != usuario.pk
        and (usuario_e_master(request.user) or not usuario_e_master(usuario))
    )
    acessos = AcessoModulo.objects.filter(usuario=usuario).exclude(
        status=AcessoModulo.Status.REVOGADO,
    ).select_related('perfil', 'concedido_por').annotate(
        total_permissoes_ativas=Count(
            'concessoes', filter=Q(concessoes__revogada_em__isnull=True),
        ),
    )
    return render(request, 'gestao/usuarios/acessos.html', {
        'usuario_alvo': usuario,
        'can_modify_target': can_modify_target,
        'acessos': acessos, 'module_labels': MODULE_LABELS,
        'historico': AuditoriaPermissao.objects.filter(
            usuario_beneficiado=usuario,
        ).select_related('permissao', 'ator')[:20],
        'section': 'Acessos e permissões',
    })


@staff_required
def usuario_acesso_form(request, uuid, acesso_uuid=None):
    if not pode_administrar_permissoes(request.user):
        raise PermissionDenied
    usuario = get_object_or_404(get_user_model(), uuid=uuid)
    if request.user.pk == usuario.pk:
        raise PermissionDenied('Não é permitido alterar os próprios acessos.')
    if usuario_e_master(usuario) and not usuario_e_master(request.user):
        raise PermissionDenied('Acessos de MASTER são protegidos.')
    acesso = get_object_or_404(AcessoModulo, uuid=acesso_uuid, usuario=usuario) if acesso_uuid else None
    raw_modulo = acesso.modulo if acesso else request.POST.get('modulo') or request.GET.get('modulo', '')
    modulo = {'yubotuka': 'media', 'eventos': 'events', 'esportes': 'sports'}.get(raw_modulo, raw_modulo)
    data = None
    if request.method == 'POST':
        data = request.POST.copy()
        data['modulo'] = modulo
    form = AcessoModuloForm(data, instance=acesso, modulo=modulo)
    if request.method == 'POST':
        if form.is_valid():
            salvar_acesso_modulo(
                ator=request.user, beneficiado=usuario, modulo=form.cleaned_data['modulo'],
                permissoes=form.cleaned_data['permissoes'], perfil=form.cleaned_data['perfil'],
                escopo=form.cleaned_data['escopo'], valida_ate=form.cleaned_data['valida_ate'],
                justificativa=form.cleaned_data['justificativa'],
                observacao=form.cleaned_data['observacao'], request=request,
            )
            messages.success(request, 'Acesso ao módulo salvo e auditado.')
            return redirect('gestao:usuario_acessos', uuid=usuario.uuid)
    grupos = defaultdict(list)
    for permissao in Permissao.objects.filter(modulo=modulo, ativo=True).order_by('grupo', 'nome'):
        grupos[permissao.grupo or 'Outras'].append(permissao)
    selecionadas = set(form['permissoes'].value() or [])
    modulos = [
        (item, MODULE_LABELS.get(item, item.title()))
        for item in Permissao.objects.exclude(modulo='').values_list('modulo', flat=True).distinct().order_by('modulo')
    ]
    perfis = Perfil.objects.filter(ativo=True, perfil_permissoes__permissao__modulo=modulo).distinct()
    return render(request, 'gestao/usuarios/acesso_form.html', {
        'usuario_alvo': usuario, 'acesso': acesso, 'modulo': modulo,
        'form': form,
        'modulos': modulos, 'grupos': dict(grupos), 'perfis': perfis,
        'selecionadas': selecionadas, 'escopos': AcessoModulo.Escopo.choices,
        'section': 'Acessos e permissões',
    })


@staff_required
@require_POST
def usuario_acesso_status(request, uuid, acesso_uuid):
    if not pode_administrar_permissoes(request.user):
        raise PermissionDenied
    usuario = get_object_or_404(get_user_model(), uuid=uuid)
    acesso = get_object_or_404(AcessoModulo, uuid=acesso_uuid, usuario=usuario)
    try:
        alterar_status_acesso(
            ator=request.user, acesso=acesso, status=request.POST.get('status', ''),
            justificativa=request.POST.get('justificativa', ''), request=request,
        )
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('gestao:usuario_acessos', uuid=usuario.uuid)

    messages.success(request, 'Situação do acesso atualizada.')
    return redirect('gestao:usuario_acessos', uuid=usuario.uuid)


def usuario_permissoes(request, uuid):
    return redirect('gestao:usuario_acessos', uuid=uuid)
from apps.locations.models import Bairro, Cidade, Estado, Pais
from apps.organizations.models import Endereco, Organizacao, Unidade
from apps.taxonomy.models import Categoria, Subcategoria

Usuario = get_user_model()


@staff_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Visão executiva e operacional, limitada ao escopo autorizado."""
    from apps.products.models import CategoriaProduto, Produto

    is_master = usuario_e_master(request.user)
    card_specs = [
        ('Usuários', Usuario, 'usuarios.visualizar', 'gestao:usuarios_lista', Q(is_active=True)),
        ('Organizações', Organizacao, 'organizacoes.gerenciar', 'gestao:organizacoes_lista', Q(ativo=True)),
        ('Categorias', Categoria, 'categorias.gerenciar', 'gestao:categorias_lista', Q(ativo=True)),
    ]
    cards = [
        {'label': label, 'total': model.objects.filter(predicate).count(),
         'url': reverse(url_name), 'detail': 'ativos'}
        for label, model, permission_code, url_name, predicate in card_specs
        if pode(request.user, permission_code)
    ]
    if pode(request.user, 'produtos.visualizar'):
        cards.append({
            'label': 'Produtos publicados',
            'total': Produto.objects.filter(status=Produto.Status.PUBLICADO, ativo=True).count(),
            'url': reverse('painel:produtos_lista'), 'detail': 'visíveis no catálogo',
        })
    if is_master or pode(request.user, 'products.taxonomy.visualizar'):
        cards.append({
            'label': 'Categorias de produto',
            'total': CategoriaProduto.objects.filter(ativo=True).count(),
            'url': reverse('gestao:taxonomia_produtos_dashboard'), 'detail': 'ativas',
        })

    pendencias = []
    if pode(request.user, 'produtos.visualizar'):
        pendencias.append({
            'label': 'Produtos aguardando análise',
            'total': Produto.objects.filter(status=Produto.Status.EM_ANALISE, ativo=True).count(),
            'url': f'{reverse("painel:produtos_lista")}?status={Produto.Status.EM_ANALISE}',
            'level': 'warning',
        })
    if is_master or pode(request.user, 'products.taxonomy.visualizar'):
        pendencias.append({
            'label': 'Produtos sem taxonomia completa',
            'total': Produto.objects.filter(
                ativo=True,
            ).filter(
                Q(categoria_taxonomia__isnull=True)
                | Q(familia__isnull=True)
                | Q(tipo_produto__isnull=True)
            ).distinct().count(),
            'url': reverse('gestao:taxonomia_produtos_dashboard'), 'level': 'warning',
        })

    operational = None
    activities = []
    insights = []
    if is_master:
        from apps.agenda.models import Agendamento
        from apps.advertising.models import AuditoriaPublicidade, Campanha, Criativo, EntregaPublicidade
        from apps.analytics.models import AnalyticsDailyCompany, AnalyticsEvent
        from apps.core.models import Auditoria
        from apps.events.models import Evento
        from apps.news.models import Artigo, EditorialStatus
        from apps.organizations.models import Empresa, EmpresaSolicitacao
        from apps.payments.models import Cobranca, Pagamento, Webhook
        from apps.products.models import Produto
        from apps.recruitment.models import Vaga
        from apps.services.models import Servico

        now = timezone.now()
        last_30_days = now.date() - timedelta(days=29)
        advertising = Campanha.objects.aggregate(
            total=Count('pk'),
            awaiting=Count('pk', filter=Q(status=Campanha.Status.AGUARDANDO_APROVACAO)),
            active=Count('pk', filter=Q(status=Campanha.Status.ATIVA)),
            rejected=Count('pk', filter=Q(status=Campanha.Status.REJEITADA)),
        )
        advertising.update(Criativo.objects.aggregate(
            creatives=Count('pk'),
            creatives_pending=Count('pk', filter=Q(aprovado=False, ativo=True)),
        ))
        advertising.update(EntregaPublicidade.objects.aggregate(
            impressions=Count('pk'),
            clicks=Count('pk', filter=Q(clicado_em__isnull=False)),
        ))
        advertising['ctr'] = (
            round(advertising['clicks'] * 100 / advertising['impressions'], 2)
            if advertising['impressions'] else 0
        )

        payments = Cobranca.objects.aggregate(
            charges=Count('pk'),
            pending=Count('pk', filter=Q(status=Cobranca.Status.PENDENTE)),
            paid=Count('pk', filter=Q(status=Cobranca.Status.PAGA)),
            paid_total=Sum('valor_total', filter=Q(status=Cobranca.Status.PAGA)),
            pending_total=Sum('valor_total', filter=Q(status=Cobranca.Status.PENDENTE)),
        )
        payments['paid_total'] = payments['paid_total'] or Decimal('0.00')
        payments['pending_total'] = payments['pending_total'] or Decimal('0.00')
        payments['failed'] = Pagamento.objects.filter(status=Pagamento.Status.FALHOU).count()
        payments['webhook_errors'] = Webhook.objects.filter(
            Q(assinatura_valida=False) | ~Q(erro=''),
        ).count()

        analytics = AnalyticsDailyCompany.objects.filter(date__gte=last_30_days).aggregate(
            impressions=Sum('impressions'), views=Sum('views'), visitors=Sum('visitors'),
            leads=Sum('leads'), whatsapp_clicks=Sum('whatsapp_clicks'),
        )
        analytics = {key: value or 0 for key, value in analytics.items()}
        analytics['events_24h'] = AnalyticsEvent.objects.filter(
            created_at__gte=now - timedelta(hours=24),
        ).count()

        operational = {
            'advertising': advertising,
            'payments': payments,
            'analytics': analytics,
            'platform': {
                'companies': Empresa.objects.aggregate(
                    total=Count('pk'),
                    active=Count('pk', filter=Q(ativo=True, status=Empresa.Status.ATIVA)),
                    pending=Count('pk', filter=Q(
                        ativo=True, status__in=(Empresa.Status.PENDENTE, Empresa.Status.EM_ANALISE),
                    )),
                ),
                'users': Usuario.objects.aggregate(
                    total=Count('pk'), active=Count('pk', filter=Q(is_active=True)),
                ),
                'content': {
                    'articles': Artigo.objects.count(),
                    'published_articles': Artigo.objects.filter(status=EditorialStatus.PUBLICADO).count(),
                    'events': Evento.objects.count(),
                    'published_events': Evento.objects.filter(status=Evento.Status.PUBLICADO, ativo=True).count(),
                },
                'products': Produto.objects.aggregate(
                    total=Count('pk'),
                    published=Count('pk', filter=Q(status=Produto.Status.PUBLICADO, ativo=True)),
                ),
                'services': Servico.objects.aggregate(
                    total=Count('pk'),
                    published=Count('pk', filter=Q(status=Servico.Status.PUBLICADO, ativo=True)),
                ),
                'appointments': Agendamento.objects.count(),
                'jobs': Vaga.objects.count(),
            },
        }
        if advertising['awaiting']:
            insights.append({
                'level': 'warning', 'title': 'Fila de publicidade',
                'text': f'{advertising["awaiting"]} campanha(s) aguardam decisão de moderação.',
            })
        if payments['failed'] or payments['webhook_errors']:
            insights.append({
                'level': 'danger', 'title': 'Atenção financeira',
                'text': (
                    f'{payments["failed"]} pagamento(s) falharam e '
                    f'{payments["webhook_errors"]} webhook(s) têm inconsistência.'
                ),
            })
        if advertising['impressions']:
            insights.append({
                'level': 'info', 'title': 'Desempenho publicitário',
                'text': f'CTR acumulado das entregas registradas: {advertising["ctr"]}%.',
            })
        if analytics['views']:
            insights.append({
                'level': 'info', 'title': 'Conversão observada',
                'text': f'{analytics["leads"]} lead(s) em {analytics["views"]} visualização(ões) nos últimos 30 dias.',
            })
        request_pending = EmpresaSolicitacao.objects.filter(
            status__in=(EmpresaSolicitacao.Status.PENDENTE, EmpresaSolicitacao.Status.EM_ANALISE),
        ).count()
        article_pending = Artigo.objects.filter(
            status__in=(EditorialStatus.ENVIADO_REVISAO, EditorialStatus.EM_REVISAO),
        ).count()
        event_pending = Evento.objects.filter(status=Evento.Status.EM_ANALISE, ativo=True).count()
        pendencias.extend([
            {'label': 'Empresas pendentes',
             'total': operational['platform']['companies']['pending'],
             'url': reverse('gestao:empresas_lista'),
             'level': 'warning'},
            {'label': 'Solicitações de empresa', 'total': request_pending,
             'url': reverse('gestao:solicitacoes_lista'), 'level': 'warning'},
            {'label': 'Artigos em revisão', 'total': article_pending,
             'url': reverse('gestao:central_lista', args=['artigos']), 'level': 'warning'},
            {'label': 'Eventos em análise', 'total': event_pending,
             'url': reverse('gestao:central_lista', args=['eventos']), 'level': 'warning'},
            {'label': 'Campanhas aguardando aprovação', 'total': advertising['awaiting'],
             'url': reverse('gestao:publicidade_campanhas'), 'level': 'warning'},
            {'label': 'Criativos aguardando aprovação', 'total': advertising['creatives_pending'],
             'url': reverse('gestao:publicidade_campanhas'), 'level': 'warning'},
            {'label': 'Cobranças pendentes', 'total': payments['pending'],
             'url': reverse('gestao:central_lista', args=['cobrancas']), 'level': 'warning'},
            {'label': 'Pagamentos com falha', 'total': payments['failed'],
             'url': reverse('gestao:central_lista', args=['pagamentos']), 'level': 'danger'},
            {'label': 'Webhooks inconsistentes', 'total': payments['webhook_errors'],
             'url': reverse('gestao:central_lista', args=['webhooks']), 'level': 'danger'},
        ])

        for item in AuditoriaPublicidade.objects.select_related('campanha', 'usuario').order_by('-criado_em')[:8]:
            activities.append({
                'when': item.criado_em, 'module': 'Advertising', 'action': item.acao,
                'subject': item.campanha.nome, 'actor': item.usuario,
            })
        for item in Auditoria.objects.select_related('usuario').order_by('-criado_em')[:8]:
            activities.append({
                'when': item.criado_em, 'module': item.origem or 'Sistema', 'action': item.acao,
                'subject': f'{item.entidade} {item.registro_id}'.strip(), 'actor': item.usuario,
            })
        activities = sorted(activities, key=lambda item: item['when'], reverse=True)[:10]

    pendencias = sorted(
        pendencias, key=lambda item: (item['total'] == 0, -item['total'], item['label']),
    )

    return render(request, 'gestao/dashboard.html', {
        'cards': cards, 'pendencias': pendencias, 'operational': operational,
        'activities': activities, 'insights': insights,
        'is_master_dashboard': is_master,
        'atualizado_em': timezone.now(), 'section': 'Visão geral',
    })


class GestaoContextMixin:
    """Contexto comum para templates de CRUD."""

    title = ''
    section = ''
    list_url_name = ''
    create_url_name = ''

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'title': self.title,
                'section': self.section,
                'list_url_name': self.list_url_name,
                'create_url_name': self.create_url_name,
            }
        )
        return context


class GestaoListView(GestaoContextMixin, DomainPermissionRequiredMixin, ListView):
    template_name = 'gestao/crud/list.html'
    paginate_by = 20
    search_fields: tuple[str, ...] = ()
    columns: tuple[tuple[str, str], ...] = ()
    edit_url_name = ''
    detail_url_name = ''

    def get_queryset(self):
        manager = getattr(self.model, 'all_objects', self.model.objects)
        queryset = manager.all().order_by(*self.model._meta.ordering)
        search = self.request.GET.get('q', '').strip()

        if search and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f'{field}__icontains': search})
            queryset = queryset.filter(query)

        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'columns': self.columns,
                'edit_url_name': self.edit_url_name,
                'detail_url_name': self.detail_url_name,
                'query': self.request.GET.get('q', ''),
            }
        )
        return context


class GestaoCreateView(GestaoContextMixin, DomainPermissionRequiredMixin, CreateView):
    template_name = 'gestao/crud/form.html'

    def get_success_url(self) -> str:
        return reverse(self.list_url_name)

    def form_valid(self, form):
        messages.success(self.request, 'Registro criado com sucesso.')
        return super().form_valid(form)


class GestaoUpdateView(GestaoContextMixin, DomainPermissionRequiredMixin, UpdateView):
    template_name = 'gestao/crud/form.html'

    def get_queryset(self):
        manager = getattr(self.model, 'all_objects', self.model.objects)
        return manager.all()

    def get_success_url(self) -> str:
        return reverse(self.list_url_name)

    def form_valid(self, form):
        messages.success(self.request, 'Registro atualizado com sucesso.')
        return super().form_valid(form)


class GestaoDetailView(GestaoContextMixin, DomainPermissionRequiredMixin, DetailView):
    template_name = 'gestao/crud/detail.html'
    columns: tuple[tuple[str, str], ...] = ()
    edit_url_name = ''
    status_url_name = ''

    def get_queryset(self):
        manager = getattr(self.model, 'all_objects', self.model.objects)
        return manager.all()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update({
            'columns': self.columns,
            'edit_url_name': self.edit_url_name,
            'status_url_name': self.status_url_name,
        })
        return context


class UsuarioDetailView(GestaoContextMixin, DomainPermissionRequiredMixin, DetailView):
    model = Usuario
    template_name = 'gestao/usuarios/detail.html'
    title = 'Usuário'
    section = 'Usuários'
    list_url_name = 'gestao:usuarios_lista'
    permission_code = 'usuarios.visualizar'

    def get_queryset(self):
        return Usuario.objects.select_related('perfil', 'estado', 'cidade').prefetch_related(
            'perfis_adicionais', 'groups', 'user_permissions',
            'capacidades_usuario__capacidade',
            'acessos_modulos__perfil',
            Prefetch(
                'concessoes_permissao',
                queryset=ConcessaoPermissao.objects.select_related(
                    'permissao', 'concedida_por',
                ).filter(revogada_em__isnull=True),
                to_attr='active_permission_grants',
            ),
            'empresas_vinculos__empresa',
            'auditorias_permissao_recebidas__permissao',
            'auditorias_permissao_recebidas__ator',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        actor_is_master = usuario_e_master(self.request.user)
        protected_target = usuario_e_master(self.object) or self.object.is_staff
        can = criar_verificador_permissoes(self.request.user)
        context.update({
            'can_edit_user': can('usuarios.editar') and (
                actor_is_master or not protected_target
            ),
            'can_manage_access': can('gestao.gerenciar_permissoes'),
            'can_change_status': can('usuarios.desativar') and (
                actor_is_master or not usuario_e_master(self.object)
            ),
            'actor_is_master': actor_is_master,
            'is_master_target': usuario_e_master(self.object),
            'company_links': self.object.empresas_vinculos.all(),
            'active_grants': self.object.active_permission_grants,
            'permission_audit': self.object.auditorias_permissao_recebidas.all()[:20],
        })
        return context


@permission_required('usuarios.desativar')
@require_POST
def usuario_desativar(request: HttpRequest, pk: int) -> HttpResponse:
    """Desativa um usuário."""

    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk == request.user.pk:
        raise PermissionDenied('Você não pode desativar a própria conta.')
    if usuario_e_master(usuario) and not usuario_e_master(request.user):
        raise PermissionDenied('Apenas MASTER pode desativar outro usuário MASTER.')
    usuario.is_active = False
    usuario.save(update_fields=['is_active', 'atualizado_em'])
    messages.success(request, 'Usuário desativado com sucesso.')
    return redirect('gestao:usuarios_lista')


@permission_required('usuarios.editar')
@require_POST
def usuario_ativar(request: HttpRequest, pk: int) -> HttpResponse:
    """Ativa um usuário."""

    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario_e_master(usuario) and not usuario_e_master(request.user):
        raise PermissionDenied('Apenas MASTER pode ativar outro usuário MASTER.')
    usuario.is_active = True
    usuario.save(update_fields=['is_active', 'atualizado_em'])
    messages.success(request, 'Usuário ativado com sucesso.')
    return redirect('gestao:usuarios_lista')


@master_required
@require_POST
def usuario_papel_global(request: HttpRequest, pk: int) -> HttpResponse:
    usuario = get_object_or_404(Usuario, pk=pk)
    papel = request.POST.get('papel', '').strip().upper()
    try:
        if papel:
            atribuir_papel_global(
                executor=request.user, usuario=usuario, papel=papel, request=request,
            )
            messages.success(request, 'Papel global atribuído e auditado.')
        else:
            if not usuario.perfil or usuario.perfil.nome.upper() not in {
                'MASTER', 'ADMIN_GLOBAL', 'SUPORTE_GLOBAL', 'AUDITOR_GLOBAL',
            }:
                raise ValidationError('O usuário não possui papel global revogável.')
            revogar_papel_global(executor=request.user, usuario=usuario, request=request)
            messages.success(request, 'Papel global revogado e auditado.')
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, '; '.join(getattr(exc, 'messages', [str(exc)])))
        if isinstance(exc, PermissionDenied):
            raise
    return redirect('gestao:usuarios_detalhe', pk=usuario.pk)


@permission_required('contatos.ativar')
@require_POST
def contato_ativar(request: HttpRequest, pk: int) -> HttpResponse:
    """Ativa um contato institucional."""

    contato = get_object_or_404(ContatoInstitucional, pk=pk)
    contato.ativo = True
    contato.save(update_fields=['ativo', 'atualizado_em'])
    messages.success(request, 'Contato ativado com sucesso.')
    return redirect('gestao:contatos_lista')


@permission_required('contatos.ativar')
@require_POST
def contato_desativar(request: HttpRequest, pk: int) -> HttpResponse:
    """Desativa um contato institucional."""

    contato = get_object_or_404(ContatoInstitucional, pk=pk)
    contato.ativo = False
    contato.save(update_fields=['ativo', 'atualizado_em'])
    messages.success(request, 'Contato desativado com sucesso.')
    return redirect('gestao:contatos_lista')


class UsuarioListView(GestaoListView):
    model = Usuario
    title = 'Usuários'
    section = 'Usuários'
    list_url_name = 'gestao:usuarios_lista'
    create_url_name = 'gestao:usuarios_novo'
    edit_url_name = 'gestao:usuarios_editar'
    detail_url_name = 'gestao:usuarios_detalhe'
    permission_code = 'usuarios.visualizar'
    search_fields = ('first_name', 'last_name', 'email', 'username', 'telefone')
    columns = (
        ('Nome', 'get_full_name'),
        ('E-mail', 'email'),
        ('Perfil', 'perfil'),
        ('Ativo', 'is_active'),
        ('Staff', 'is_staff'),
    )
    template_name = 'gestao/usuarios/list.html'

    def get_queryset(self):
        now = timezone.now()
        queryset = super().get_queryset().select_related('perfil').annotate(
            acesso_gestao_registrado=Exists(
                AcessoModulo.objects.filter(
                    usuario_id=OuterRef('pk'), modulo='gestao',
                    status=AcessoModulo.Status.ATIVO,
                ).filter(Q(valida_ate__isnull=True) | Q(valida_ate__gt=now))
            ),
        ).order_by('email', 'pk')
        active = self.request.GET.get('ativo', '')
        staff = self.request.GET.get('staff', '')
        profile = self.request.GET.get('perfil', '')
        gestao = self.request.GET.get('gestao', '')
        if active in {'1', '0'}:
            queryset = queryset.filter(is_active=active == '1')
        if staff in {'1', '0'}:
            queryset = queryset.filter(is_staff=staff == '1')
        if profile.isdigit():
            queryset = queryset.filter(perfil_id=profile)
        if gestao in {'1', '0'}:
            has_gestao = (
                Q(acesso_gestao_registrado=True)
                | Q(is_superuser=True)
                | Q(perfil__nome__iexact='MASTER', perfil__ativo=True, perfil__removido_em__isnull=True)
                | Q(
                    usuario_perfis_adicionais__perfil__nome__iexact='MASTER',
                    usuario_perfis_adicionais__perfil__ativo=True,
                    usuario_perfis_adicionais__perfil__removido_em__isnull=True,
                )
            )
            queryset = queryset.filter(has_gestao if gestao == '1' else ~has_gestao).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can = criar_verificador_permissoes(self.request.user)
        context.update({
            'user_filters': True,
            'active_filter': self.request.GET.get('ativo', ''),
            'staff_filter': self.request.GET.get('staff', ''),
            'profile_filter': self.request.GET.get('perfil', ''),
            'gestao_filter': self.request.GET.get('gestao', ''),
            'profiles': Perfil.objects.filter(ativo=True).order_by('nome'),
            'can_create_user': can('usuarios.criar'),
            'can_edit_user': can('usuarios.editar'),
            'can_change_status': can('usuarios.desativar'),
            'can_manage_access': can('gestao.gerenciar_permissoes'),
            'actor_is_master': usuario_e_master(self.request.user),
        })
        return context


class UsuarioCreateView(GestaoCreateView):
    model = Usuario
    form_class = UsuarioCreateForm
    title = 'Novo usuário'
    section = 'Usuários'
    list_url_name = 'gestao:usuarios_lista'
    permission_code = 'usuarios.criar'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['ator'] = self.request.user
        return kwargs


class UsuarioUpdateView(GestaoUpdateView):
    model = Usuario
    form_class = UsuarioForm
    title = 'Editar usuário'
    section = 'Usuários'
    list_url_name = 'gestao:usuarios_lista'
    permission_code = 'usuarios.editar'

    def dispatch(self, request, *args, **kwargs):
        alvo = self.get_object()
        if (usuario_e_master(alvo) or alvo.is_staff) and not usuario_e_master(request.user):
            raise PermissionDenied('Apenas MASTER pode alterar contas administrativas protegidas.')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['ator'] = self.request.user
        return kwargs


class PerfilListView(GestaoListView):
    model = Perfil
    title = 'Perfis'
    section = 'Perfis'
    list_url_name = 'gestao:perfis_lista'
    create_url_name = 'gestao:perfis_novo'
    edit_url_name = 'gestao:perfis_editar'
    permission_code = 'perfis.gerenciar'
    search_fields = ('nome', 'descricao')
    columns = (('Nome', 'nome'), ('Ativo', 'ativo'), ('Criado em', 'criado_em'))


class PerfilCreateView(GestaoCreateView):
    model = Perfil
    form_class = PerfilForm
    title = 'Novo perfil'
    section = 'Perfis'
    list_url_name = 'gestao:perfis_lista'
    permission_code = 'perfis.gerenciar'
    master_only = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['ator'] = self.request.user
        return kwargs


class PerfilUpdateView(GestaoUpdateView):
    model = Perfil
    form_class = PerfilForm
    title = 'Editar perfil'
    section = 'Perfis'
    list_url_name = 'gestao:perfis_lista'
    permission_code = 'perfis.gerenciar'
    master_only = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['ator'] = self.request.user
        return kwargs


@master_required
def perfil_permissoes(request: HttpRequest, pk: int) -> HttpResponse:
    """Permite vincular permissões de domínio a um perfil."""

    perfil = get_object_or_404(Perfil.all_objects, pk=pk)

    if request.method == 'POST':
        selecionadas = set(request.POST.getlist('permissoes'))
        PerfilPermissao.all_objects.filter(perfil=perfil).update(ativo=False)

        for permissao in Permissao.all_objects.filter(pk__in=selecionadas):
            vinculo, _created = PerfilPermissao.all_objects.get_or_create(
                perfil=perfil,
                permissao=permissao,
            )
            vinculo.ativo = True
            vinculo.removido_em = None
            vinculo.save(update_fields=['ativo', 'removido_em', 'atualizado_em'])

        messages.success(request, 'Permissões do perfil atualizadas com sucesso.')
        return redirect('gestao:perfil_permissoes', pk=perfil.pk)

    permissoes_ativas = set(
        PerfilPermissao.objects.filter(perfil=perfil).values_list('permissao_id', flat=True)
    )
    grupos = defaultdict(list)
    for permissao in Permissao.objects.filter(ativo=True).order_by('modulo', 'grupo', 'nome'):
        grupos[permissao.modulo or permissao.codigo.split('.', 1)[0]].append(permissao)

    return render(
        request,
        'gestao/perfis/permissoes.html',
        {
            'perfil': perfil,
            'grupos': [
                {
                    'codigo': modulo,
                    'nome': 'Produtos' if modulo == 'products' else modulo.replace('_', ' ').title(),
                    'permissoes': permissoes,
                }
                for modulo, permissoes in grupos.items()
            ],
            'permissoes_ativas': permissoes_ativas,
            'usuarios_vinculados': perfil.usuarios.count(),
            'title': 'Permissões do perfil',
            'section': 'Perfis',
        },
    )


class PermissaoListView(GestaoListView):
    model = Permissao
    title = 'Permissões'
    section = 'Permissões'
    list_url_name = 'gestao:permissoes_lista'
    create_url_name = 'gestao:permissoes_nova'
    edit_url_name = 'gestao:permissoes_editar'
    permission_code = 'perfis.gerenciar'
    search_fields = ('nome', 'codigo', 'descricao')
    columns = (('Nome', 'nome'), ('Código', 'codigo'), ('Ativo', 'ativo'))


class PermissaoCreateView(GestaoCreateView):
    model = Permissao
    form_class = PermissaoForm
    title = 'Nova permissão'
    section = 'Permissões'
    list_url_name = 'gestao:permissoes_lista'
    permission_code = 'perfis.gerenciar'
    master_only = True


class PermissaoUpdateView(GestaoUpdateView):
    model = Permissao
    form_class = PermissaoForm
    title = 'Editar permissão'
    section = 'Permissões'
    list_url_name = 'gestao:permissoes_lista'
    permission_code = 'perfis.gerenciar'
    master_only = True


@master_required
def controle_detalhe(request: HttpRequest, kind: str, pk: int) -> HttpResponse:
    configs = {'perfis': Perfil, 'permissoes': Permissao}
    if kind not in configs:
        raise PermissionDenied
    instance = get_object_or_404(configs[kind].all_objects, pk=pk)
    return render(request, 'gestao/acessos/detail.html', {
        'object': instance, 'kind': kind,
        'title': 'Perfil' if kind == 'perfis' else 'Permissão',
        'list_url_name': f'gestao:{kind}_lista',
        'edit_url_name': f'gestao:{kind}_editar',
        'section': 'Acessos',
    })


@master_required
@require_POST
def controle_status(request: HttpRequest, kind: str, pk: int) -> HttpResponse:
    configs = {'perfis': Perfil, 'permissoes': Permissao}
    if kind not in configs:
        raise PermissionDenied
    instance = get_object_or_404(configs[kind].all_objects, pk=pk)
    if kind == 'perfis' and instance.nome.upper() == 'MASTER':
        raise PermissionDenied('O perfil MASTER não pode ser inativado.')
    if kind == 'permissoes' and instance.protegida:
        raise PermissionDenied('Permissões protegidas não podem ser inativadas.')
    instance.ativo = not instance.ativo
    instance.removido_em = None if instance.ativo else timezone.now()
    instance.save(update_fields=['ativo', 'removido_em', 'atualizado_em'])
    messages.success(request, 'Status atualizado com segurança.')
    return redirect('gestao:controle_detalhe', kind=kind, pk=pk)


CRUD_CONFIGS = {
    'organizacoes': (Organizacao, OrganizacaoForm, 'Organizações', 'organizacoes.gerenciar', ('nome_fantasia', 'documento', 'email')),
    'unidades': (Unidade, UnidadeForm, 'Unidades', 'organizacoes.gerenciar', ('nome', 'email', 'organizacao__nome_fantasia')),
    'enderecos': (Endereco, EnderecoForm, 'Endereços', 'organizacoes.gerenciar', ('logradouro', 'cep', 'cidade__nome')),
    'categorias': (Categoria, CategoriaForm, 'Categorias', 'categorias.gerenciar', ('nome', 'slug')),
    'subcategorias': (Subcategoria, SubcategoriaForm, 'Subcategorias', 'categorias.gerenciar', ('nome', 'slug', 'categoria__nome')),
    'paises': (Pais, PaisForm, 'Países', 'localidades.gerenciar', ('nome', 'codigo_iso_2', 'codigo_iso_3')),
    'estados': (Estado, EstadoForm, 'Estados', 'localidades.gerenciar', ('nome', 'sigla', 'pais__nome')),
    'cidades': (Cidade, CidadeForm, 'Cidades', 'localidades.gerenciar', ('nome', 'codigo_ibge', 'estado__sigla')),
    'bairros': (Bairro, BairroForm, 'Bairros', 'localidades.gerenciar', ('nome', 'cidade__nome')),
    'configuracoes': (ConfiguracaoSistema, ConfiguracaoSistemaForm, 'Configurações', 'configuracoes.gerenciar', ('chave', 'valor', 'descricao')),
    'contatos': (ContatoInstitucional, ContatoInstitucionalForm, 'Contatos', 'contatos.visualizar', ('nome', 'valor', 'url')),
}

CRUD_CREATE_PERMISSIONS = {
    'contatos': 'contatos.criar',
}

CRUD_EDIT_PERMISSIONS = {
    'contatos': 'contatos.editar',
}


def build_list_view(slug: str):
    model, _form, title, permission_code, search_fields = CRUD_CONFIGS[slug]
    columns = (('Nome', '__str__'), ('Ativo', 'ativo'), ('Atualizado em', 'atualizado_em'))

    if slug == 'contatos':
        columns = (
            ('Nome', 'nome'),
            ('Tipo', 'tipo'),
            ('Valor', 'valor'),
            ('Topbar', 'exibir_topbar'),
            ('Rodapé', 'exibir_rodape'),
            ('Ativo', 'ativo'),
        )

    return GestaoListView.as_view(
        model=model,
        title=title,
        section=title,
        list_url_name=f'gestao:{slug}_lista',
        create_url_name=f'gestao:{slug}_novo',
        edit_url_name=f'gestao:{slug}_editar',
        detail_url_name=(
            f'gestao:{slug}_detalhe'
            if slug in {'organizacoes', 'unidades', 'enderecos', 'categorias', 'subcategorias', 'paises', 'estados', 'cidades', 'bairros'} else ''
        ),
        permission_code=permission_code,
        search_fields=search_fields,
        columns=columns,
        master_only=slug == 'configuracoes',
    )


def build_detail_view(slug: str):
    model, _form, title, permission_code, _search_fields = CRUD_CONFIGS[slug]
    return GestaoDetailView.as_view(
        model=model,
        title=title.rstrip('s'),
        section=title,
        list_url_name=f'gestao:{slug}_lista',
        edit_url_name=f'gestao:{slug}_editar',
        status_url_name=f'gestao:{slug}_status',
        permission_code=permission_code,
        columns=(
            ('Registro', '__str__'),
            ('Ativo', 'ativo'),
            ('Criado em', 'criado_em'),
            ('Atualizado em', 'atualizado_em'),
        ),
    )


@staff_required
@require_POST
def crud_status(request: HttpRequest, slug: str, pk: int) -> HttpResponse:
    if slug not in {'organizacoes', 'unidades', 'enderecos', 'categorias', 'subcategorias', 'paises', 'estados', 'cidades', 'bairros'}:
        raise PermissionDenied
    model, _form, _title, permission_code, _search_fields = CRUD_CONFIGS[slug]
    if not pode(request.user, permission_code):
        raise PermissionDenied
    manager = getattr(model, 'all_objects', model.objects)
    instance = get_object_or_404(manager, pk=pk)
    instance.ativo = not instance.ativo
    update_fields = ['ativo', 'atualizado_em']
    if hasattr(instance, 'removido_em'):
        instance.removido_em = None if instance.ativo else timezone.now()
        update_fields.append('removido_em')
    instance.save(update_fields=update_fields)
    messages.success(request, 'Registro ativado.' if instance.ativo else 'Registro inativado sem exclusão física.')
    return redirect(f'gestao:{slug}_detalhe', pk=instance.pk)


def build_create_view(slug: str):
    model, form_class, title, permission_code, _search_fields = CRUD_CONFIGS[slug]
    return GestaoCreateView.as_view(
        model=model,
        form_class=form_class,
        title=f'Novo registro - {title}',
        section=title,
        list_url_name=f'gestao:{slug}_lista',
        permission_code=CRUD_CREATE_PERMISSIONS.get(slug, permission_code),
        master_only=slug == 'configuracoes',
    )


def build_update_view(slug: str):
    model, form_class, title, permission_code, _search_fields = CRUD_CONFIGS[slug]
    return GestaoUpdateView.as_view(
        model=model,
        form_class=form_class,
        title=f'Editar registro - {title}',
        section=title,
        list_url_name=f'gestao:{slug}_lista',
        permission_code=CRUD_EDIT_PERMISSIONS.get(slug, permission_code),
        master_only=slug == 'configuracoes',
    )
