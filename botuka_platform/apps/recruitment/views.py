from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.organizations.permissions import empresas_disponiveis_para_usuario, usuario_pode_gerenciar_empresa
from apps.organizations.models import Empresa
from .forms import (CandidaturaForm, ContatoPublicoForm, CursoForm,
                    CurriculoPrivacidadeForm, ExperienciaForm, FormacaoForm,
                    HabilidadeForm, IdiomaForm, InformacaoAdicionalForm,
                    PerfilProfissionalForm, ProjetoForm, PublicacaoCurriculoForm,
                    VagaForm)
from .models import (Candidatura, Curso, Curriculo, CurriculoInformacaoAdicional,
                     CurriculoPrivacidade, Experiencia, Formacao, Habilidade,
                     Idioma, Projeto, Vaga)
from .services import calcular_progresso, concluir_curriculo, curriculo_para_painel, curriculo_publico
from .services.curriculum import atualizar_etapa_atual


def _vaga_usuario(usuario, uuid):
    return get_object_or_404(Vaga.objects.filter(empresa__in=empresas_disponiveis_para_usuario(usuario)), uuid=uuid)


@login_required
def vaga_lista(request):
    vagas = Vaga.objects.filter(empresa__in=empresas_disponiveis_para_usuario(request.user)).select_related('empresa')
    return render(request, 'painel/vagas/lista.html', {'titulo': 'Vagas', 'vagas': vagas})


@login_required
def vaga_criar(request):
    form = VagaForm(request.POST or None, usuario=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            vaga = form.save(commit=False)
            vaga.usuario_responsavel = request.user
            vaga.save()
        messages.success(request, 'Vaga cadastrada com sucesso.')
        return redirect('painel:vaga_detalhe', uuid=vaga.uuid)
    return render(request, 'painel/recruitment/form.html', {'titulo': 'Nova vaga', 'form': form})


@login_required
def vaga_detalhe(request, uuid):
    return render(request, 'painel/vagas/detalhe.html', {'vaga': _vaga_usuario(request.user, uuid)})


@login_required
def vaga_editar(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if not usuario_pode_gerenciar_empresa(request.user, vaga.empresa): raise PermissionDenied
    form = VagaForm(request.POST or None, instance=vaga, usuario=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic(): form.save()
        messages.success(request, 'Vaga atualizada com sucesso.')
        return redirect('painel:vaga_detalhe', uuid=vaga.uuid)
    return render(request, 'painel/recruitment/form.html', {'titulo': 'Editar vaga', 'form': form})


@login_required
def vaga_status(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if request.method != 'POST' or not usuario_pode_gerenciar_empresa(request.user, vaga.empresa): raise PermissionDenied
    status = request.POST.get('status')
    if status not in Vaga.Status.values: raise Http404
    vaga.status = status
    vaga.save()
    return redirect('painel:vaga_detalhe', uuid=vaga.uuid)


@login_required
def vaga_excluir(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    if request.method != 'POST' or not usuario_pode_gerenciar_empresa(request.user, vaga.empresa): raise PermissionDenied
    vaga.delete()
    return redirect('painel:vagas_lista')


def vagas_publicas(request):
    queryset = Vaga.objects.filter(status=Vaga.Status.PUBLICADA, publicado_em__isnull=False, empresa__ativo=True, empresa__perfil_publico=True, empresa__status=Empresa.Status.ATIVA, empresa__excluido_em__isnull=True).filter(Q(encerramento__isnull=True) | Q(encerramento__gte=timezone.localdate())).select_related('empresa')
    q = request.GET.get('q', '').strip()[:100]
    if q: queryset = queryset.filter(Q(titulo__icontains=q) | Q(descricao__icontains=q) | Q(requisitos__icontains=q) | Q(empresa__nome_fantasia__icontains=q) | Q(bairro__icontains=q))
    if request.GET.get('modalidade'): queryset = queryset.filter(modalidade__iexact=request.GET['modalidade'][:30])
    if request.GET.get('contrato'): queryset = queryset.filter(tipo_contrato__iexact=request.GET['contrato'][:40])
    if request.GET.get('bairro'): queryset = queryset.filter(bairro__iexact=request.GET['bairro'][:100])
    if request.GET.get('pcd') == '1': queryset = queryset.filter(aceita_pcd=True)
    ordem = request.GET.get('ordem')
    queryset = queryset.order_by('encerramento' if ordem == 'prazo' else 'titulo' if ordem == 'az' else '-publicado_em')
    page = Paginator(queryset, 12).get_page(request.GET.get('page'))
    return render(request, 'publico/vagas/lista.html', {'vagas': page.object_list, 'page_obj': page, 'total': page.paginator.count})


def vaga_publica(request, slug):
    return render(request, 'publico/vagas/detalhe.html', {'vaga': get_object_or_404(Vaga.objects.select_related('empresa'), slug=slug, status=Vaga.Status.PUBLICADA)})


def curriculo_publico_view(request, uuid):
    objeto = get_object_or_404(
        Curriculo.objects.select_related('privacidade').prefetch_related(
            'experiencia_set', 'formacao_set', 'curso_set', 'habilidades',
            'idiomas', 'projetos',
        ), uuid=uuid,
        status=Curriculo.Status.CONCLUIDO,
        visibilidade=Curriculo.Visibilidade.PUBLICO,
        ativo=True, excluido_em__isnull=True,
    )
    dto = curriculo_publico(objeto)
    if dto is None: raise Http404
    return render(request, 'publico/vagas/curriculo.html', {'curriculo': dto})


@login_required
def candidatar(request, slug):
    vaga = get_object_or_404(Vaga.objects, slug=slug, status=Vaga.Status.PUBLICADA)
    curriculo = get_object_or_404(
        Curriculo.objects, usuario=request.user,
        status=Curriculo.Status.CONCLUIDO,
        visibilidade__in=[Curriculo.Visibilidade.CANDIDATURAS, Curriculo.Visibilidade.PUBLICO],
    )
    form = CandidaturaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                candidatura = form.save(commit=False); candidatura.vaga = vaga; candidatura.usuario = request.user; candidatura.curriculo = curriculo; candidatura.save()
            messages.success(request, 'Candidatura enviada.')
        except (IntegrityError,):
            messages.error(request, 'Você já possui uma candidatura ativa para esta vaga.')
        return redirect('recruitment_public:vaga', slug=slug)
    return render(request, 'painel/recruitment/form.html', {'titulo': 'Candidatar-se', 'form': form})


@login_required
def minhas_candidaturas(request):
    return render(request, 'painel/candidaturas/lista.html', {'candidaturas': Candidatura.objects.filter(usuario=request.user).select_related('vaga')})


@login_required
def candidaturas_empresa(request, uuid):
    vaga = _vaga_usuario(request.user, uuid)
    return render(request, 'painel/candidaturas/lista.html', {'candidaturas': vaga.candidaturas.select_related('usuario', 'curriculo'), 'vaga': vaga})


def _curriculo_usuario(usuario):
    return Curriculo.objects.filter(usuario=usuario, ativo=True, excluido_em__isnull=True).first()


@login_required
def curriculo_detalhe(request):
    curriculo = _curriculo_usuario(request.user)
    return render(request, 'painel/curriculo/index.html', {
        'curriculo': curriculo,
        'progresso': calcular_progresso(curriculo) if curriculo else None,
    })


@login_required
def curriculo_novo(request):
    if _curriculo_usuario(request.user):
        return redirect('painel:curriculo_etapa', etapa=1)
    form = PerfilProfissionalForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            curriculo = form.save(commit=False)
            curriculo.usuario = request.user
            curriculo.etapa_atual = 1
            curriculo.status = Curriculo.Status.EM_PREENCHIMENTO
            curriculo.save()
            CurriculoPrivacidade.objects.create(curriculo=curriculo)
        messages.success(request, 'Currículo criado. Continue preenchendo as próximas etapas.')
        return redirect('painel:curriculo_etapa', etapa=2)
    return render(request, 'painel/curriculo/etapa.html', {'form': form, 'etapa': 1, 'total_etapas': 10, 'curriculo': None, 'progresso': None})


ETAPAS = {
    1: ('Perfil profissional', PerfilProfissionalForm),
    2: ('Contato público', ContatoPublicoForm),
    3: ('Experiências profissionais', None),
    4: ('Formação acadêmica', None),
    5: ('Cursos e certificações', None),
    6: ('Habilidades', None),
    7: ('Idiomas', None),
    8: ('Projetos e portfólio', None),
    9: ('Informações adicionais', InformacaoAdicionalForm),
    10: ('Privacidade e publicação', PublicacaoCurriculoForm),
}


@login_required
def curriculo_etapa(request, etapa):
    if etapa not in ETAPAS: raise Http404
    curriculo = _curriculo_usuario(request.user)
    if not curriculo: return redirect('painel:curriculo_novo')
    redirects = {3: 'painel:curriculo_experiencias', 4: 'painel:curriculo_formacoes',
                 5: 'painel:curriculo_cursos', 6: 'painel:curriculo_habilidades',
                 7: 'painel:curriculo_idiomas', 8: 'painel:curriculo_projetos'}
    if etapa in redirects: return redirect(redirects[etapa])
    titulo, form_class = ETAPAS[etapa]
    if etapa == 9:
        instance, _ = CurriculoInformacaoAdicional.objects.get_or_create(curriculo=curriculo)
        form = form_class(request.POST or None, instance=instance)
        privacy_form = None
    elif etapa == 10:
        privacy, _ = CurriculoPrivacidade.objects.get_or_create(curriculo=curriculo)
        form = form_class(request.POST or None, instance=curriculo)
        privacy_form = CurriculoPrivacidadeForm(request.POST or None, instance=privacy, prefix='privacidade')
    else:
        form = form_class(request.POST or None, instance=curriculo)
        privacy_form = None
    if request.method == 'POST' and form.is_valid() and (privacy_form is None or privacy_form.is_valid()):
        with transaction.atomic():
            form.save()
            if privacy_form: privacy_form.save()
            atualizar_etapa_atual(curriculo, etapa)
            if request.POST.get('acao') == 'concluir':
                try: concluir_curriculo(curriculo)
                except ValueError as exc: messages.error(request, str(exc))
                else: return redirect('painel:curriculo_visualizar')
        messages.success(request, 'Etapa salva com sucesso.')
        if request.POST.get('acao') == 'rascunho': return redirect('painel:curriculo')
        return redirect('painel:curriculo_etapa', etapa=min(etapa + 1, 10))
    return render(request, 'painel/curriculo/etapa.html', {'form': form, 'privacy_form': privacy_form, 'titulo': titulo, 'etapa': etapa, 'total_etapas': 10, 'curriculo': curriculo, 'progresso': calcular_progresso(curriculo), 'etapas': ETAPAS})


@login_required
def curriculo_editar(request):
    return redirect('painel:curriculo_etapa', etapa=1)


def _itens(request, model, form_class, titulo, etapa, lista_url, route_prefix, item_uuid=None, remover=False):
    curriculo = _curriculo_usuario(request.user)
    if not curriculo:
        if item_uuid: raise Http404
        return redirect('painel:curriculo_novo')
    queryset = model.objects.filter(curriculo=curriculo, ativo=True, excluido_em__isnull=True)
    item = get_object_or_404(queryset, uuid=item_uuid) if item_uuid else None
    if remover:
        if request.method == 'POST':
            item.delete(); messages.success(request, 'Item removido.'); return redirect(lista_url)
        return render(request, 'painel/curriculo/remover.html', {'item': item, 'titulo': titulo})
    form = form_class(request.POST or None, request.FILES or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        registro = form.save(commit=False); registro.curriculo = curriculo; registro.save()
        atualizar_etapa_atual(curriculo, etapa)
        messages.success(request, 'Item salvo com sucesso.')
        return redirect(lista_url)
    return render(request, 'painel/curriculo/itens.html', {'titulo': titulo, 'form': form, 'itens': queryset, 'item': item, 'etapa': etapa, 'progresso': calcular_progresso(curriculo), 'curriculo': curriculo, 'lista_url_name': lista_url, 'novo_url_name': f'painel:{route_prefix}_nova' if route_prefix in {'curriculo_experiencia', 'curriculo_formacao', 'curriculo_habilidade'} else f'painel:{route_prefix}_novo', 'editar_url_name': f'painel:{route_prefix}_editar', 'remover_url_name': f'painel:{route_prefix}_remover'})


def _crud(model, form, titulo, etapa, lista_url, route_prefix):
    def view(request, uuid=None): return _itens(request, model, form, titulo, etapa, lista_url, route_prefix, uuid, request.resolver_match.url_name.endswith('_remover'))
    return login_required(view)

curriculo_experiencias = _crud(Experiencia, ExperienciaForm, 'Experiências profissionais', 3, 'painel:curriculo_experiencias', 'curriculo_experiencia')
curriculo_formacoes = _crud(Formacao, FormacaoForm, 'Formações acadêmicas', 4, 'painel:curriculo_formacoes', 'curriculo_formacao')
curriculo_cursos = _crud(Curso, CursoForm, 'Cursos e certificações', 5, 'painel:curriculo_cursos', 'curriculo_curso')
curriculo_habilidades = _crud(Habilidade, HabilidadeForm, 'Habilidades', 6, 'painel:curriculo_habilidades', 'curriculo_habilidade')
curriculo_idiomas = _crud(Idioma, IdiomaForm, 'Idiomas', 7, 'painel:curriculo_idiomas', 'curriculo_idioma')
curriculo_projetos = _crud(Projeto, ProjetoForm, 'Projetos e portfólio', 8, 'painel:curriculo_projetos', 'curriculo_projeto')


@login_required
def curriculo_visualizar(request):
    curriculo = _curriculo_usuario(request.user)
    if not curriculo: return redirect('painel:curriculo_novo')
    return render(request, 'painel/curriculo/preview.html', {'curriculo': curriculo_para_painel(curriculo), 'progresso': calcular_progresso(curriculo), 'objeto': curriculo})


curriculo_preview = curriculo_visualizar
