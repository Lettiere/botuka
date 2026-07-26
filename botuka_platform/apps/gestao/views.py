"""Views do painel interno de gestão."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Model, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.models import ConfiguracaoSistema, ContatoInstitucional, Perfil, Permissao
from apps.gestao.decorators import (
    DomainPermissionRequiredMixin,
    master_required,
    permission_required,
    staff_required,
)
from apps.accounts.permissions import usuario_e_master
from apps.accounts.models import ConcessaoPermissao
from apps.accounts.permission_services import (
    conceder_permissao, pode_administrar_permissoes, revogar_permissao,
)
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
    UsuarioCreateForm,
    UsuarioForm,
)


@staff_required
def usuario_permissoes(request, uuid):
    if not pode_administrar_permissoes(request.user):
        raise PermissionDenied
    usuario = get_object_or_404(get_user_model(), uuid=uuid)
    if request.method == 'POST':
        justificativa = request.POST.get('justificativa', '')
        if request.POST.get('acao') == 'revogar':
            concessao = get_object_or_404(
                ConcessaoPermissao, uuid=request.POST.get('concessao'),
                usuario=usuario,
            )
            revogar_permissao(
                ator=request.user, concessao=concessao,
                justificativa=justificativa, request=request,
            )
            messages.success(request, 'Permissão revogada e auditada.')
        else:
            permissao = get_object_or_404(
                Permissao.objects, uuid=request.POST.get('permissao'),
            )
            conceder_permissao(
                ator=request.user, beneficiado=usuario,
                permissao=permissao, justificativa=justificativa,
                observacao=request.POST.get('observacao', ''), request=request,
            )
            messages.success(request, 'Permissão concedida e auditada.')
        return redirect('gestao:usuario_permissoes', uuid=usuario.uuid)
    return render(request, 'gestao/usuarios/permissoes.html', {
        'usuario_alvo': usuario,
        'permissoes': Permissao.objects.order_by('modulo', 'grupo', 'codigo'),
        'concessoes': ConcessaoPermissao.objects.filter(
            usuario=usuario, revogada_em__isnull=True,
        ).select_related('permissao', 'concedida_por'),
        'section': 'Permissões individuais',
    })
from apps.locations.models import Bairro, Cidade, Estado, Pais
from apps.organizations.models import Endereco, Organizacao, Unidade
from apps.taxonomy.models import Categoria, Subcategoria

Usuario = get_user_model()


@staff_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Página inicial do painel interno."""

    cards = [
        ('Usuários', Usuario.objects.count(), 'gestao:usuarios_lista'),
        ('Perfis', Perfil.objects.count(), 'gestao:perfis_lista'),
        ('Permissões', Permissao.objects.count(), 'gestao:permissoes_lista'),
        ('Organizações', Organizacao.objects.count(), 'gestao:organizacoes_lista'),
        ('Unidades', Unidade.objects.count(), 'gestao:unidades_lista'),
        ('Categorias', Categoria.objects.count(), 'gestao:categorias_lista'),
    ]
    return render(request, 'gestao/dashboard.html', {'cards': cards})


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


class UsuarioDetailView(GestaoContextMixin, DomainPermissionRequiredMixin, DetailView):
    model = Usuario
    template_name = 'gestao/usuarios/detail.html'
    title = 'Usuário'
    section = 'Usuários'
    list_url_name = 'gestao:usuarios_lista'
    permission_code = 'usuarios.visualizar'


@permission_required('usuarios.desativar')
def usuario_desativar(request: HttpRequest, pk: int) -> HttpResponse:
    """Desativa um usuário."""

    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario_e_master(usuario) and not usuario_e_master(request.user):
        raise PermissionDenied('Apenas MASTER pode desativar outro usuário MASTER.')
    usuario.is_active = False
    usuario.save(update_fields=['is_active', 'atualizado_em'])
    messages.success(request, 'Usuário desativado com sucesso.')
    return redirect('gestao:usuarios_lista')


@permission_required('usuarios.editar')
def usuario_ativar(request: HttpRequest, pk: int) -> HttpResponse:
    """Ativa um usuário."""

    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario_e_master(usuario) and not usuario_e_master(request.user):
        raise PermissionDenied('Apenas MASTER pode ativar outro usuário MASTER.')
    usuario.is_active = True
    usuario.save(update_fields=['is_active', 'atualizado_em'])
    messages.success(request, 'Usuário ativado com sucesso.')
    return redirect('gestao:usuarios_lista')


@permission_required('contatos.ativar')
def contato_ativar(request: HttpRequest, pk: int) -> HttpResponse:
    """Ativa um contato institucional."""

    contato = get_object_or_404(ContatoInstitucional, pk=pk)
    contato.ativo = True
    contato.save(update_fields=['ativo', 'atualizado_em'])
    messages.success(request, 'Contato ativado com sucesso.')
    return redirect('gestao:contatos_lista')


@permission_required('contatos.ativar')
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
        if usuario_e_master(alvo) and not usuario_e_master(request.user):
            raise PermissionDenied('Apenas MASTER pode alterar outro usuário MASTER.')
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
    for permissao in Permissao.all_objects.all().order_by('codigo'):
        modulo = permissao.codigo.split('.', 1)[0]
        grupos[modulo].append(permissao)

    return render(
        request,
        'gestao/perfis/permissoes.html',
        {
            'perfil': perfil,
            'grupos': dict(grupos),
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
        permission_code=permission_code,
        search_fields=search_fields,
        columns=columns,
        master_only=slug == 'configuracoes',
    )


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
