"""Formulários do painel de gestão."""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from apps.accounts.permissions import usuario_e_master
from apps.accounts.models import AcessoModulo

from apps.core.models import (
    ConfiguracaoSistema,
    ContatoInstitucional,
    Perfil,
    PerfilPermissao,
    Permissao,
)
from apps.locations.models import Bairro, Cidade, Estado, Pais
from apps.organizations.models import (
    Capacidade, CNAE, Empresa, EmpresaCapacidade, EmpresaCNAE, EmpresaFuncao,
    EmpresaSolicitacao, EmpresaUsuario, SubcategoriaCNAE,
    Endereco, Organizacao, Unidade,
)
from apps.taxonomy.models import Categoria, Subcategoria
from apps.painel.forms import cpf_valido, somente_digitos
from apps.painel.forms import EmpresaForm, EmpresaUsuarioForm

Usuario = get_user_model()
GLOBAL_PROFILE_NAMES = ('MASTER', 'ADMIN_GLOBAL', 'SUPORTE_GLOBAL', 'AUDITOR_GLOBAL')
MODULE_ALIASES = {'yubotuka': 'media', 'eventos': 'events', 'esportes': 'sports'}


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


class EmpresaGestaoForm(EmpresaForm):
    """Cadastro global que preserva todas as validações do formulário operacional."""

    class Meta(EmpresaForm.Meta):
        fields = [
            'usuario_proprietario', *EmpresaForm.Meta.fields,
            'origem_cadastro', 'ativo',
        ]

    def __init__(self, *args, ator=None, **kwargs):
        self.ator = ator
        super().__init__(*args, usuario=ator, pode_alterar_status=True, **kwargs)
        self.fields['origem_cadastro'].disabled = bool(self.instance.pk)
        self.fields['usuario_proprietario'].queryset = self.fields[
            'usuario_proprietario'
        ].queryset.filter(is_active=True).order_by('email')
        if self.instance.pk:
            self.fields['usuario_proprietario'].disabled = True
            self.fields['usuario_proprietario'].help_text = (
                'Somente um fluxo auditado de propriedade pode alterar o proprietário atual.'
            )
        if not self.instance.pk:
            self.fields['usuario_proprietario'].required = True
            self.fields['usuario_proprietario'].help_text = (
                'O proprietário inicial receberá o vínculo administrativo da empresa.'
            )
            self.fields['origem_cadastro'].initial = Empresa.OrigemCadastro.ADMIN


class EmpresaVinculoGestaoForm(EmpresaUsuarioForm):
    """Vínculo global reutilizando validação de usuário, papel e duplicidade."""

    pass


class EmpresaSolicitacaoGestaoForm(BaseGestaoModelForm):
    class Meta:
        model = EmpresaSolicitacao
        fields = ['status', 'motivo_decisao']

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status')
        if status in {
            EmpresaSolicitacao.Status.REJEITADA,
            EmpresaSolicitacao.Status.CORRECAO_SOLICITADA,
        } and not (cleaned.get('motivo_decisao') or '').strip():
            self.add_error('motivo_decisao', 'Informe o motivo desta decisão.')
        return cleaned


class EmpresaCapacidadeGestaoForm(BaseGestaoModelForm):
    class Meta:
        model = EmpresaCapacidade
        fields = ['status', 'motivo_rejeicao', 'ativo']

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get('status') == EmpresaCapacidade.Status.REJEITADA
            and not (cleaned.get('motivo_rejeicao') or '').strip()
        ):
            self.add_error('motivo_rejeicao', 'Informe o motivo da rejeição.')
        return cleaned


class CapacidadeGestaoForm(BaseGestaoModelForm):
    class Meta:
        model = Capacidade
        fields = ['codigo', 'nome', 'descricao', 'exige_aprovacao', 'ativo']


class EmpresaFuncaoGestaoForm(BaseGestaoModelForm):
    class Meta:
        model = EmpresaFuncao
        fields = ['codigo', 'nome', 'descricao', 'ativo']


class CNAEGestaoForm(BaseGestaoModelForm):
    class Meta:
        model = CNAE
        fields = [
            'codigo', 'descricao', 'secao', 'secao_descricao', 'divisao',
            'divisao_descricao', 'grupo', 'grupo_descricao', 'classe',
            'classe_descricao', 'subclasse', 'fonte', 'versao', 'ativo',
        ]


class SubcategoriaCNAEGestaoForm(BaseGestaoModelForm):
    class Meta:
        model = SubcategoriaCNAE
        fields = ['subcategoria', 'cnae', 'relevancia', 'principal', 'revisado', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subcategoria'].queryset = Subcategoria.all_objects.filter(
            Q(ativo=True) | Q(pk=getattr(self.instance, 'subcategoria_id', None)),
        ).select_related('categoria').order_by('categoria__nome', 'ordem', 'nome')
        self.fields['cnae'].queryset = CNAE.objects.filter(
            Q(ativo=True) | Q(pk=getattr(self.instance, 'cnae_id', None)),
        ).order_by('codigo')


class EmpresaCNAEGestaoForm(BaseGestaoModelForm):
    class Meta:
        model = EmpresaCNAE
        fields = ['empresa', 'cnae', 'principal', 'origem', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['empresa'].queryset = Empresa.all_objects.filter(
            Q(ativo=True) | Q(pk=getattr(self.instance, 'empresa_id', None)),
        ).order_by('nome_fantasia')
        self.fields['cnae'].queryset = CNAE.objects.filter(
            Q(ativo=True) | Q(pk=getattr(self.instance, 'cnae_id', None)),
        ).order_by('codigo')

    def clean(self):
        cleaned = super().clean()
        empresa = cleaned.get('empresa')
        if empresa and cleaned.get('principal') and cleaned.get('ativo'):
            duplicate = EmpresaCNAE.objects.filter(
                empresa=empresa, principal=True, ativo=True,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error('principal', 'A empresa já possui um CNAE principal ativo.')
        return cleaned


class AcessoModuloForm(forms.ModelForm):
    """Valida módulo, perfil e matriz sem consultar UUIDs vazios manualmente."""

    modulo = forms.ChoiceField(label='Módulo')
    perfil = forms.ModelChoiceField(
        queryset=Perfil.objects.none(), required=False,
        empty_label='Sem perfil predefinido',
    )
    permissoes = forms.ModelMultipleChoiceField(
        queryset=Permissao.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = AcessoModulo
        fields = ['modulo', 'perfil', 'escopo', 'valida_ate', 'justificativa', 'observacao']
        widgets = {'valida_ate': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

    def __init__(self, *args, modulo='', **kwargs):
        super().__init__(*args, **kwargs)
        modules = list(
            Permissao.objects.exclude(modulo='').values_list('modulo', flat=True)
            .distinct().order_by('modulo')
        )
        self.fields['modulo'].choices = [(value, value.title()) for value in modules]
        selected = MODULE_ALIASES.get(
            (self.data.get('modulo') if self.is_bound else modulo or getattr(self.instance, 'modulo', '')),
            (self.data.get('modulo') if self.is_bound else modulo or getattr(self.instance, 'modulo', '')),
        )
        self.selected_module = selected
        self.fields['perfil'].queryset = Perfil.objects.filter(
            ativo=True, perfil_permissoes__permissao__modulo=selected,
        ).distinct()
        self.fields['permissoes'].queryset = Permissao.objects.filter(
            ativo=True, modulo=selected,
        ).order_by('grupo', 'nome')
        if self.instance.pk and not self.is_bound:
            self.fields['permissoes'].initial = self.instance.concessoes.filter(
                revogada_em__isnull=True,
            ).values_list('permissao_id', flat=True)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.setdefault('class', 'form-control')

    def clean_modulo(self):
        modulo = MODULE_ALIASES.get(self.cleaned_data['modulo'], self.cleaned_data['modulo'])
        if not Permissao.objects.filter(modulo=modulo, ativo=True).exists():
            raise forms.ValidationError('Selecione um módulo válido.')
        if self.instance.pk and modulo != self.instance.modulo:
            raise forms.ValidationError('O módulo de um acesso existente não pode ser alterado.')
        return modulo

    def clean(self):
        cleaned = super().clean()
        modulo = cleaned.get('modulo')
        perfil = cleaned.get('perfil')
        if perfil and not PerfilPermissao.objects.filter(
            perfil=perfil, ativo=True, permissao__modulo=modulo,
        ).exists():
            self.add_error('perfil', 'O perfil selecionado não pertence a este módulo.')
        permissoes = cleaned.get('permissoes') or ()
        if not perfil and not permissoes:
            self.add_error('permissoes', 'Selecione ao menos uma permissão ou um perfil inicial.')
        for permissao in permissoes:
            if permissao.modulo != modulo:
                self.add_error('permissoes', 'Todas as permissões devem pertencer ao módulo selecionado.')
                break
        return cleaned


class UsuarioForm(BaseGestaoModelForm):
    """Formulário administrativo de usuários sem edição direta de senha."""

    cpf = forms.CharField(label='CPF', required=False, max_length=14)

    def __init__(self, *args: object, ator=None, **kwargs: object) -> None:
        self.ator = ator
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self._era_master = usuario_e_master(self.instance)
        global_profiles = self.fields['perfil'].queryset.filter(nome__in=GLOBAL_PROFILE_NAMES)
        if not usuario_e_master(ator):
            self.fields['perfil'].queryset = self.fields['perfil'].queryset.exclude(nome__in=GLOBAL_PROFILE_NAMES)
        if self.instance.pk and self.instance.perfil_id in global_profiles.values_list('pk', flat=True):
            self.fields['perfil'].disabled = True
            self.fields['perfil'].help_text = 'Use a ação protegida de papel global no detalhe do usuário.'
        if self.instance.pk and usuario_e_master(self.instance):
            self.fields['is_staff'].disabled = True
            self.fields['is_staff'].help_text = (
                'Contas MASTER só podem perder privilégios pelo fluxo protegido de papel global.'
            )
        if not usuario_e_master(ator):
            self.fields['is_staff'].disabled = True
            self.fields['is_staff'].help_text = 'Somente MASTER pode alterar o acesso administrativo.'

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

    def clean(self):
        cleaned = super().clean()
        if not usuario_e_master(self.ator):
            if self.instance.pk:
                original = Usuario.objects.get(pk=self.instance.pk)
                cleaned['is_staff'] = original.is_staff
            else:
                cleaned['is_staff'] = False
        if self.instance.pk == getattr(self.ator, 'pk', None):
            if cleaned.get('is_active') is False:
                self.add_error('is_active', 'Você não pode desativar a própria conta.')
            if usuario_e_master(self.instance) and cleaned.get('perfil') != self.instance.perfil:
                self.add_error('perfil', 'Use o fluxo protegido de papéis globais.')
            if usuario_e_master(self.instance) and cleaned.get('is_staff') is False:
                self.add_error('is_staff', 'O MASTER não pode remover o próprio acesso administrativo.')
        return cleaned

    def save(self, commit: bool = True):
        usuario = super().save(commit=False)
        is_new = usuario._state.adding
        papel_global = (
            usuario.perfil.nome.upper()
            if usuario.perfil and usuario.perfil.nome.upper() in GLOBAL_PROFILE_NAMES else None
        )
        if papel_global:
            usuario.perfil = None
        usuario.username = usuario.email.lower()
        usuario.email = usuario.email.lower()

        if is_new:
            usuario.set_unusable_password()

        if commit:
            usuario.save()
            self.save_m2m()
            if papel_global:
                from apps.organizations.services.institutional import atribuir_papel_global
                atribuir_papel_global(executor=self.ator, usuario=usuario, papel=papel_global)

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
        fields = [
            'modulo', 'grupo', 'nome', 'codigo', 'descricao',
            'criticidade', 'protegida', 'ativo',
        ]


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = Categoria.all_objects.filter(
            Q(ativo=True) | Q(pk=getattr(self.instance, 'categoria_id', None)),
        ).order_by('ordem', 'nome')


class PaisForm(BaseGestaoModelForm):
    class Meta:
        model = Pais
        fields = ['nome', 'nome_oficial', 'codigo_iso_2', 'codigo_iso_3', 'ativo']

    def clean_codigo_iso_2(self):
        return self.cleaned_data['codigo_iso_2'].strip().upper()

    def clean_codigo_iso_3(self):
        return self.cleaned_data['codigo_iso_3'].strip().upper()


class EstadoForm(BaseGestaoModelForm):
    class Meta:
        model = Estado
        fields = ['pais', 'nome', 'sigla', 'codigo_ibge', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pais'].queryset = Pais.all_objects.filter(
            Q(ativo=True) | Q(pk=getattr(self.instance, 'pais_id', None)),
        ).order_by('nome')

    def clean_sigla(self):
        return self.cleaned_data['sigla'].strip().upper()


class CidadeForm(BaseGestaoModelForm):
    class Meta:
        model = Cidade
        fields = ['estado', 'nome', 'codigo_ibge', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado'].queryset = Estado.all_objects.filter(
            Q(ativo=True) | Q(pk=getattr(self.instance, 'estado_id', None)),
        ).select_related('pais').order_by('pais__nome', 'nome')


class BairroForm(BaseGestaoModelForm):
    class Meta:
        model = Bairro
        fields = ['cidade', 'nome', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cidade'].queryset = Cidade.all_objects.filter(
            Q(ativo=True) | Q(pk=getattr(self.instance, 'cidade_id', None)),
        ).select_related('estado').order_by('estado__sigla', 'nome')


class ConfiguracaoSistemaForm(BaseGestaoModelForm):
    class Meta:
        model = ConfiguracaoSistema
        fields = ['chave', 'valor', 'descricao', 'ativo']

    SENSITIVE_MARKERS = ('SECRET', 'TOKEN', 'PASSWORD', 'SENHA', 'CREDENTIAL', 'PRIVATE_KEY')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        key = getattr(self.instance, 'chave', '').upper()
        if self.instance.pk and any(marker in key for marker in self.SENSITIVE_MARKERS):
            self.fields['valor'].disabled = True
            self.fields['valor'].required = False
            self.fields['valor'].widget = forms.PasswordInput(
                attrs={'class': 'form-control', 'autocomplete': 'new-password'},
                render_value=False,
            )
            self.fields['valor'].help_text = 'Valor protegido: não é exibido nem alterado pela Gestão.'


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
