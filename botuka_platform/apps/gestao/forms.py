"""Formulários do painel de gestão."""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from apps.accounts.permissions import usuario_e_master

from apps.core.models import (
    ConfiguracaoSistema,
    ContatoInstitucional,
    Perfil,
    PerfilPermissao,
    Permissao,
)
from apps.locations.models import Bairro, Cidade, Estado, Pais
from apps.organizations.models import Endereco, Organizacao, Unidade
from apps.taxonomy.models import Categoria, Subcategoria
from apps.painel.forms import cpf_valido, somente_digitos

Usuario = get_user_model()
GLOBAL_PROFILE_NAMES = ('MASTER', 'ADMIN_GLOBAL', 'SUPORTE_GLOBAL', 'AUDITOR_GLOBAL')


class BaseGestaoModelForm(forms.ModelForm):
    """Aplica classes CSS comuns aos campos do painel."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs.setdefault('class', 'form-select')
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select')
            else:
                widget.attrs.setdefault('class', 'form-control')


class UsuarioForm(BaseGestaoModelForm):
    """Formulário administrativo de usuários sem edição direta de senha."""

    cpf = forms.CharField(label='CPF', required=False, max_length=14)

    def __init__(self, *args: object, ator=None, **kwargs: object) -> None:
        self.ator = ator
        super().__init__(*args, **kwargs)
        self._era_master = usuario_e_master(self.instance)
        if not usuario_e_master(ator):
            self.fields['perfil'].queryset = self.fields['perfil'].queryset.exclude(nome__in=GLOBAL_PROFILE_NAMES)

    class Meta:
        model = Usuario
        fields = [
            'first_name',
            'last_name',
            'nome_exibicao',
            'email',
            'telefone',
            'celular',
            'foto',
            'cpf',
            'data_nascimento',
            'biografia',
            'estado',
            'cidade',
            'perfil',
            'is_active',
            'is_staff',
        ]
        labels = {
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'email': 'E-mail',
            'cpf': 'CPF',
            'is_active': 'Ativo',
            'is_staff': 'Equipe administrativa',
        }
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'biografia': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_cpf(self) -> str:
        cpf = somente_digitos(self.cleaned_data.get('cpf', ''))

        if not cpf:
            return ''

        if not cpf_valido(cpf):
            raise forms.ValidationError('CPF inválido.')

        queryset = Usuario.objects.filter(cpf=cpf)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError('Este CPF já está vinculado a outro usuário.')

        return cpf

    def clean_email(self) -> str:
        email = self.cleaned_data['email'].lower()
        queryset = Usuario.objects.filter(username=email)

        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError('Este e-mail já está cadastrado.')

        return email

    def clean_perfil(self):
        perfil = self.cleaned_data.get('perfil')
        if perfil and perfil.nome.upper() in GLOBAL_PROFILE_NAMES and not usuario_e_master(self.ator):
            raise forms.ValidationError('Apenas um usuário MASTER pode atribuir papéis globais.')
        return perfil

    def save(self, commit: bool = True):
        usuario = super().save(commit=False)
        is_new = usuario._state.adding
        usuario.username = usuario.email.lower()
        usuario.email = usuario.email.lower()

        perfil_master = usuario.perfil and usuario.perfil.nome.upper() == 'MASTER'
        if perfil_master:
            usuario.is_active = True
            usuario.is_staff = True
            usuario.is_superuser = True
        elif self._era_master and usuario_e_master(self.ator):
            usuario.is_superuser = False

        if is_new:
            usuario.set_unusable_password()

        if commit:
            usuario.save()
            self.save_m2m()

        return usuario


class UsuarioCreateForm(UsuarioForm):
    """Formulário de criação de usuário administrativo."""

    class Meta(UsuarioForm.Meta):
        fields = UsuarioForm.Meta.fields


class PerfilForm(BaseGestaoModelForm):
    """Formulário de perfil com seleção de permissões."""

    permissoes = forms.ModelMultipleChoiceField(
        queryset=Permissao.objects.all(),
        required=False,
        label='Permissões',
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 10}),
    )

    class Meta:
        model = Perfil
        fields = ['nome', 'descricao', 'ativo', 'permissoes']

    def __init__(self, *args: object, ator=None, **kwargs: object) -> None:
        self.ator = ator
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            self.fields['permissoes'].initial = Permissao.objects.filter(
                perfil_permissoes__perfil=self.instance,
                perfil_permissoes__ativo=True,
            )

    def clean_nome(self) -> str:
        nome = self.cleaned_data['nome'].strip()
        if nome.upper() == 'MASTER' and not usuario_e_master(self.ator):
            raise forms.ValidationError('Apenas um usuário MASTER pode criar ou alterar este perfil.')
        return nome

    def save(self, commit: bool = True):
        perfil = super().save(commit=commit)

        if commit:
            selecionadas = set(self.cleaned_data['permissoes'])
            PerfilPermissao.all_objects.filter(perfil=perfil).update(ativo=False)

            for permissao in selecionadas:
                vinculo, _created = PerfilPermissao.all_objects.get_or_create(
                    perfil=perfil,
                    permissao=permissao,
                )
                if not vinculo.ativo:
                    vinculo.ativo = True
                    vinculo.removido_em = None
                    vinculo.save(update_fields=['ativo', 'removido_em', 'atualizado_em'])

        return perfil


class PermissaoForm(BaseGestaoModelForm):
    class Meta:
        model = Permissao
        fields = ['nome', 'codigo', 'descricao', 'ativo']


class OrganizacaoForm(BaseGestaoModelForm):
    class Meta:
        model = Organizacao
        fields = [
            'proprietario',
            'categoria',
            'razao_social',
            'nome_fantasia',
            'documento',
            'email',
            'telefone',
            'site',
            'ativo',
        ]


class UnidadeForm(BaseGestaoModelForm):
    class Meta:
        model = Unidade
        fields = [
            'organizacao',
            'responsavel',
            'categoria',
            'nome',
            'principal',
            'email',
            'telefone',
            'ativo',
        ]


class EnderecoForm(BaseGestaoModelForm):
    class Meta:
        model = Endereco
        fields = [
            'unidade',
            'cidade',
            'bairro',
            'logradouro',
            'numero',
            'complemento',
            'cep',
            'latitude',
            'longitude',
            'ativo',
        ]


class CategoriaForm(BaseGestaoModelForm):
    class Meta:
        model = Categoria
        fields = ['nome', 'slug', 'descricao', 'icone', 'ordem', 'ativo']


class SubcategoriaForm(BaseGestaoModelForm):
    class Meta:
        model = Subcategoria
        fields = ['categoria', 'nome', 'slug', 'descricao', 'ordem', 'ativo']


class PaisForm(BaseGestaoModelForm):
    class Meta:
        model = Pais
        fields = ['nome', 'nome_oficial', 'codigo_iso_2', 'codigo_iso_3', 'ativo']


class EstadoForm(BaseGestaoModelForm):
    class Meta:
        model = Estado
        fields = ['pais', 'nome', 'sigla', 'codigo_ibge', 'ativo']


class CidadeForm(BaseGestaoModelForm):
    class Meta:
        model = Cidade
        fields = ['estado', 'nome', 'codigo_ibge', 'ativo']


class BairroForm(BaseGestaoModelForm):
    class Meta:
        model = Bairro
        fields = ['cidade', 'nome', 'ativo']


class ConfiguracaoSistemaForm(BaseGestaoModelForm):
    class Meta:
        model = ConfiguracaoSistema
        fields = ['chave', 'valor', 'descricao', 'ativo']


class ContatoInstitucionalForm(BaseGestaoModelForm):
    class Meta:
        model = ContatoInstitucional
        fields = [
            'tipo',
            'nome',
            'valor',
            'url',
            'icone',
            'ordem',
            'ativo',
            'exibir_topbar',
            'exibir_rodape',
        ]
        help_texts = {
            'valor': 'Telefone, e-mail, usuário ou descrição do contato.',
            'url': 'Link completo quando for rede social ou URL personalizada.',
            'icone': 'Classe do Bootstrap Icons, por exemplo bi-whatsapp.',
        }
