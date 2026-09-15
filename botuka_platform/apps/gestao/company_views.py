"""Administração global do domínio empresarial real."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.gestao.decorators import master_required, permission_required
from apps.gestao.forms import (
    EmpresaCapacidadeGestaoForm,
    EmpresaGestaoForm,
    EmpresaSolicitacaoGestaoForm,
    EmpresaVinculoGestaoForm,
    CapacidadeGestaoForm, EmpresaFuncaoGestaoForm,
)
from apps.organizations.models import (
    Empresa,
    EmpresaCapacidade,
    EmpresaSolicitacao,
    EmpresaUsuario,
    Capacidade, EmpresaFuncao,
    EmpresaCNAE, EmpresaPropriedade,
)
from apps.locations.models import Cidade
from apps.taxonomy.models import Categoria

CATALOGS = {
    'capacidades': (Capacidade, CapacidadeGestaoForm, 'Capacidades'),
    'funcoes': (EmpresaFuncao, EmpresaFuncaoGestaoForm, 'Funções empresariais'),
}

def _catalog(kind):
    if kind not in CATALOGS:
        from django.http import Http404
        raise Http404
    return CATALOGS[kind]


@master_required
def catalogo_lista(request, kind):
    model, _form, title = _catalog(kind)
    query = request.GET.get('q', '').strip()[:120]
    queryset = model.objects.all().order_by('nome')
    if query:
        queryset = queryset.filter(Q(codigo__icontains=query) | Q(nome__icontains=query))
    page_obj = Paginator(queryset, 25).get_page(request.GET.get('page'))
    return render(request, 'gestao/empresas/catalogo_lista.html', {
        'kind': kind, 'title': title, 'page_obj': page_obj, 'query': query,
        'section': 'Empresas',
    })


@master_required
def catalogo_form(request, kind, pk=None):
    model, form_class, title = _catalog(kind)
    instance = get_object_or_404(model, pk=pk) if pk else None
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, 'Configuração empresarial salva.')
        return redirect('gestao:empresa_catalogo_detalhe', kind=kind, pk=saved.pk)
    return render(request, 'gestao/empresas/catalogo_form.html', {
        'form': form, 'object': instance, 'title': f'{"Editar" if instance else "Nova"} — {title}',
        'section': 'Empresas', 'kind': kind,
    })


@master_required
def catalogo_detalhe(request, kind, pk):
    model, _form, title = _catalog(kind)
    instance = get_object_or_404(model, pk=pk)
    return render(request, 'gestao/empresas/catalogo_detalhe.html', {
        'kind': kind, 'title': title, 'object': instance, 'section': 'Empresas',
    })


@master_required
@require_POST
def catalogo_status(request, kind, pk):
    model, _form, _title = _catalog(kind)
    instance = get_object_or_404(model, pk=pk)
    instance.ativo = not instance.ativo
    instance.save(update_fields=['ativo', 'atualizado_em'])
    messages.success(request, 'Status atualizado.')
    return redirect('gestao:empresa_catalogo_detalhe', kind=kind, pk=pk)


def _empresa_queryset():
    return Empresa.all_objects.select_related(
        'usuario_proprietario', 'categoria_empresa', 'subcategoria_empresa',
        'cidade', 'estado', 'criado_por',
    )


@permission_required('empresas.gerenciar')
def empresa_lista(request):
    queryset = _empresa_queryset().annotate(
        propriedade_atual_registrada=Exists(
            EmpresaPropriedade.objects.filter(
                empresa_id=OuterRef('pk'), atual=True, fim_em__isnull=True,
            )
        ),
    )
    query = request.GET.get('q', '').strip()[:120]
    status = request.GET.get('status', '')
    ativo = request.GET.get('ativo', '')
    tipo = request.GET.get('tipo', '')
    origem = request.GET.get('origem', '')
    categoria = request.GET.get('categoria', '')
    cidade = request.GET.get('cidade', '')
    propriedade = request.GET.get('propriedade', '')
    if query:
        digits = ''.join(char for char in query if char.isdigit())
        queryset = queryset.filter(
            Q(nome_fantasia__icontains=query)
            | Q(razao_social__icontains=query)
            | Q(cpf_cnpj__icontains=digits or query)
            | Q(usuario_proprietario__email__icontains=query)
        )
    if status in Empresa.Status.values:
        queryset = queryset.filter(status=status)
    if ativo in {'1', '0'}:
        queryset = queryset.filter(ativo=ativo == '1')
    if tipo in Empresa.TipoCadastro.values:
        queryset = queryset.filter(tipo_cadastro=tipo)
    if origem in Empresa.OrigemCadastro.values:
        queryset = queryset.filter(origem_cadastro=origem)
    if categoria.isdigit():
        queryset = queryset.filter(categoria_empresa_id=categoria)
    if cidade.isdigit():
        queryset = queryset.filter(cidade_id=cidade)
    if propriedade in {'1', '0'}:
        queryset = queryset.filter(
            propriedade_atual_registrada=propriedade == '1',
        )
    page_obj = Paginator(queryset.order_by('-atualizado_em', 'nome_fantasia'), 25).get_page(
        request.GET.get('page'),
    )
    querystring = request.GET.copy()
    querystring.pop('page', None)
    return render(request, 'gestao/empresas/lista.html', {
        'page_obj': page_obj, 'query': query, 'status': status, 'ativo': ativo,
        'tipo': tipo, 'origem': origem, 'categoria': categoria,
        'cidade': cidade, 'propriedade': propriedade,
        'status_choices': Empresa.Status.choices,
        'type_choices': Empresa.TipoCadastro.choices,
        'origin_choices': Empresa.OrigemCadastro.choices,
        'categories': Categoria.objects.filter(ativo=True).order_by('nome'),
        'cities': Cidade.objects.filter(ativo=True).select_related('estado').order_by('nome'),
        'querystring': querystring.urlencode(), 'section': 'Empresas',
    })


@permission_required('empresas.gerenciar')
def empresa_detalhe(request, uuid):
    empresa = get_object_or_404(_empresa_queryset(), uuid=uuid)
    return render(request, 'gestao/empresas/detalhe.html', {
        'empresa': empresa,
        'vinculos': empresa.usuarios_vinculados.select_related('usuario').order_by('-ativo', 'usuario__email'),
        'propriedades': empresa.propriedades.select_related('usuario', 'aprovado_por').order_by('-inicio_em'),
        'solicitacoes': empresa.solicitacoes.select_related('usuario_solicitante', 'analisado_por').order_by('-criado_em')[:20],
        'capacidades': empresa.capacidades_empresa.select_related('capacidade', 'aprovado_por').order_by('capacidade__nome'),
        'enderecos': empresa.enderecos_empresa.select_related('endereco').order_by('-principal', '-criado_em'),
        'links': empresa.links.order_by('ordem', 'titulo'),
        'cnaes': EmpresaCNAE.objects.filter(empresa=empresa).select_related(
            'cnae',
        ).order_by('-principal', '-ativo', 'cnae__codigo'),
        'section': 'Empresas',
    })


@permission_required('empresas.gerenciar')
def empresa_form(request, uuid=None):
    empresa = get_object_or_404(Empresa.all_objects, uuid=uuid) if uuid else None
    form = EmpresaGestaoForm(
        request.POST or None, request.FILES or None, instance=empresa, ator=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            is_new = not saved.pk
            if is_new:
                saved.criado_por = request.user
                saved.origem_cadastro = Empresa.OrigemCadastro.ADMIN
            saved.save()
            form.save_m2m()
            if is_new:
                EmpresaUsuario.objects.create(
                    empresa=saved,
                    usuario=saved.usuario_proprietario,
                    funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
                    proprietario=True,
                    administrador=True,
                    pode_editar=True,
                    pode_publicar_servico=True,
                    pode_gerenciar_equipe=True,
                    convidado_por=request.user,
                    autorizado_por=request.user,
                )
        messages.success(request, 'Empresa salva com sucesso.')
        return redirect('gestao:empresa_detalhe', uuid=saved.uuid)
    return render(request, 'gestao/crud/form.html', {
        'form': form, 'object': empresa,
        'title': 'Editar empresa' if empresa else 'Nova empresa',
        'section': 'Empresas', 'list_url_name': 'gestao:empresas_lista',
    })


@permission_required('empresas.gerenciar')
@require_POST
def empresa_inativar(request, uuid):
    empresa = get_object_or_404(Empresa.all_objects, uuid=uuid)
    if empresa.ativo:
        empresa.ativo = False
        empresa.perfil_publico = False
        empresa.excluido_em = timezone.now()
        empresa.save(update_fields=['ativo', 'perfil_publico', 'excluido_em', 'atualizado_em'])
        messages.success(request, 'Empresa inativada sem apagar seu histórico.')
    return redirect('gestao:empresa_detalhe', uuid=empresa.uuid)


@permission_required('empresas.gerenciar')
@require_POST
def empresa_reativar(request, uuid):
    empresa = get_object_or_404(Empresa.all_objects, uuid=uuid)
    empresa.ativo = True
    empresa.excluido_em = None
    empresa.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])
    messages.success(request, 'Empresa reativada. A publicação permanece condicionada ao status.')
    return redirect('gestao:empresa_detalhe', uuid=empresa.uuid)


@permission_required('empresas.gerenciar')
def empresa_vinculo_form(request, empresa_uuid, pk=None):
    empresa = get_object_or_404(Empresa.all_objects, uuid=empresa_uuid)
    vinculo = get_object_or_404(EmpresaUsuario, pk=pk, empresa=empresa) if pk else None
    if vinculo and vinculo.proprietario:
        raise PermissionDenied('O vínculo proprietário deve ser alterado pelo fluxo de propriedade.')
    form = EmpresaVinculoGestaoForm(
        request.POST or None, instance=vinculo, empresa=empresa, ator=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Vínculo empresarial salvo com sucesso.')
        return redirect('gestao:empresa_detalhe', uuid=empresa.uuid)
    return render(request, 'gestao/empresas/relacao_form.html', {
        'form': form, 'empresa': empresa, 'object': vinculo,
        'title': 'Editar vínculo' if vinculo else 'Novo vínculo',
        'section': 'Empresas',
    })


@permission_required('empresas.gerenciar')
@require_POST
def empresa_vinculo_inativar(request, empresa_uuid, pk):
    empresa = get_object_or_404(Empresa.all_objects, uuid=empresa_uuid)
    vinculo = get_object_or_404(EmpresaUsuario, pk=pk, empresa=empresa)
    if vinculo.proprietario or empresa.usuario_proprietario_id == vinculo.usuario_id:
        raise PermissionDenied('O proprietário atual não pode ser removido por esta ação.')
    vinculo.ativo = False
    vinculo.save(update_fields=['ativo', 'atualizado_em'])
    messages.success(request, 'Vínculo inativado.')
    return redirect('gestao:empresa_detalhe', uuid=empresa.uuid)


@permission_required('empresas.gerenciar')
@require_POST
def empresa_vinculo_reativar(request, empresa_uuid, pk):
    empresa = get_object_or_404(Empresa.all_objects, uuid=empresa_uuid)
    vinculo = get_object_or_404(EmpresaUsuario, pk=pk, empresa=empresa)
    vinculo.ativo = True
    vinculo.save(update_fields=['ativo', 'atualizado_em'])
    messages.success(request, 'Vínculo reativado.')
    return redirect('gestao:empresa_detalhe', uuid=empresa.uuid)


@permission_required('empresas.gerenciar')
def solicitacao_lista(request):
    queryset = EmpresaSolicitacao.objects.select_related(
        'empresa', 'usuario_solicitante', 'analisado_por',
    )
    query = request.GET.get('q', '').strip()[:120]
    status = request.GET.get('status', '')
    tipo = request.GET.get('tipo', '')
    if query:
        queryset = queryset.filter(
            Q(empresa__nome_fantasia__icontains=query)
            | Q(cnpj__icontains=''.join(c for c in query if c.isdigit()) or query)
            | Q(usuario_solicitante__email__icontains=query)
        )
    if status in EmpresaSolicitacao.Status.values:
        queryset = queryset.filter(status=status)
    if tipo in EmpresaSolicitacao.TipoSolicitacao.values:
        queryset = queryset.filter(tipo_solicitacao=tipo)
    page_obj = Paginator(queryset.order_by('-criado_em'), 25).get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)
    return render(request, 'gestao/empresas/solicitacoes.html', {
        'page_obj': page_obj, 'query': query, 'status': status, 'tipo': tipo,
        'status_choices': EmpresaSolicitacao.Status.choices,
        'type_choices': EmpresaSolicitacao.TipoSolicitacao.choices,
        'querystring': querystring.urlencode(),
        'section': 'Solicitações empresariais',
    })


@permission_required('empresas.gerenciar')
def solicitacao_analisar(request, pk):
    solicitacao = get_object_or_404(
        EmpresaSolicitacao.objects.select_related('empresa', 'usuario_solicitante'), pk=pk,
    )
    form = EmpresaSolicitacaoGestaoForm(request.POST or None, instance=solicitacao)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        saved.analisado_por = request.user
        saved.analisado_em = timezone.now()
        saved.save()
        messages.success(request, 'Solicitação analisada e registrada.')
        return redirect('gestao:solicitacoes_lista')
    return render(request, 'gestao/empresas/solicitacao_form.html', {
        'form': form, 'solicitacao': solicitacao,
        'title': 'Analisar solicitação', 'section': 'Solicitações empresariais',
    })


@permission_required('empresas.gerenciar')
def capacidade_editar(request, empresa_uuid, pk):
    empresa = get_object_or_404(Empresa.all_objects, uuid=empresa_uuid)
    vinculo = get_object_or_404(
        EmpresaCapacidade.objects.select_related('capacidade'), pk=pk, empresa=empresa,
    )
    form = EmpresaCapacidadeGestaoForm(request.POST or None, instance=vinculo)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        if saved.status == EmpresaCapacidade.Status.APROVADA:
            saved.aprovado_por = request.user
            saved.aprovado_em = timezone.now()
            saved.motivo_rejeicao = ''
        else:
            saved.aprovado_por = None
            saved.aprovado_em = None
        saved.save()
        messages.success(request, 'Capacidade atualizada.')
        return redirect('gestao:empresa_detalhe', uuid=empresa.uuid)
    return render(request, 'gestao/empresas/relacao_form.html', {
        'form': form, 'empresa': empresa, 'object': vinculo,
        'title': f'Capacidade — {vinculo.capacidade.nome}', 'section': 'Empresas',
    })
