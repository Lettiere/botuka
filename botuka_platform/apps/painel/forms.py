"""Formulários da área interna do usuário."""

from __future__ import annotations

import re

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError

from apps.core.models import EnderecoCore, PessoaDocumento
from apps.organizations.models import Empresa, EmpresaLink, EmpresaUsuario
from apps.organizations.models import EmpresaCapacidade, EmpresaSolicitacao
from apps.organizations.permissions import empresas_disponiveis_para_usuario
from apps.services.models import (
    Servico,
    ServicoArea,
    ServicoCaracteristica,
    ServicoImagem,
    ServicoLink,
)

Usuario = get_user_model()


def somente_digitos(valor: str) -> str:
    return re.sub(r'\D', '', valor or '')


def cpf_valido(cpf: str) -> bool:
    """Valida CPF com dígitos verificadores."""

    cpf = somente_digitos(cpf)

    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * ((tamanho + 1) - i) for i in range(tamanho))
        digito = ((soma * 10) % 11) % 10
        if digito != int(cpf[tamanho]):
            return False

    return True


def cnpj_valido(cnpj: str) -> bool:
    """Valida CNPJ com dígitos verificadores."""

    cnpj = somente_digitos(cnpj)

    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    pesos = ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    for indice, peso in enumerate(pesos):
        soma = sum(int(cnpj[i]) * peso[i] for i in range(len(peso)))
        digito = 11 - (soma % 11)
        digito = 0 if digito >= 10 else digito
        if digito != int(cnpj[12 + indice]):
            return False

    return True


class BasePerfilForm(forms.ModelForm):
    """Base visual dos forms públicos de perfil."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class DadosPessoaisForm(BasePerfilForm):
    class Meta:
        model = Usuario
        fields = [
            'first_name',
            'last_name',
            'nome_exibicao',
            'data_nascimento',
            'estado',
            'cidade',
        ]
        labels = {
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'nome_exibicao': 'Nome de exibição',
            'data_nascimento': 'Data de nascimento',
        }
        help_texts = {
            'nome_exibicao': 'Nome público exibido no BOTUKA.',
            'cidade': 'Cidade principal do seu perfil.',
        }
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
        }


class ContatoUsuarioForm(BasePerfilForm):
    email = forms.EmailField(
        label='E-mail',
        required=False,
        disabled=True,
        help_text='A alteração de e-mail será feita em fluxo próprio.',
    )

    class Meta:
        model = Usuario
        fields = ['email', 'telefone', 'celular']
        help_texts = {
            'telefone': 'Telefone para contato.',
            'celular': 'Celular ou WhatsApp pessoal.',
        }


class FotoPerfilForm(BasePerfilForm):
    class Meta:
        model = Usuario
        fields = ['foto']
        help_texts = {
            'foto': 'Use uma imagem clara para seu avatar.',
        }


class DocumentoUsuarioForm(BasePerfilForm):
    cpf = forms.CharField(
        label='CPF',
        required=False,
        max_length=14,
        help_text='Opcional no cadastro básico. Necessário em ações de publicação, compra, venda ou contratação.',
    )

    class Meta:
        model = Usuario
        fields = ['cpf']

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


class ApresentacaoUsuarioForm(BasePerfilForm):
    class Meta:
        model = Usuario
        fields = ['biografia']
        labels = {'biografia': 'Biografia curta'}
        help_texts = {
            'biografia': 'Conte brevemente quem você é ou o que faz.',
        }
        widgets = {
            'biografia': forms.Textarea(attrs={'rows': 4, 'maxlength': 500}),
        }


class EmpresaForm(forms.ModelForm):
    """Form principal para cadastro e edição de empresas no painel."""

    class Meta:
        model = Empresa
        fields = [
            'tipo_cadastro',
            'razao_social',
            'nome_fantasia',
            'cpf_cnpj',
            'inscricao_estadual',
            'inscricao_municipal',
            'categoria_empresa',
            'descricao_curta',
            'descricao_completa',
            'telefone',
            'whatsapp',
            'email',
            'site',
            'logo',
            'imagem_capa',
            'cep',
            'endereco',
            'numero',
            'complemento',
            'bairro',
            'estado',
            'cidade',
            'atende_online',
            'atende_local',
            'horario_atendimento',
            'perfil_publico',
            'status',
        ]
        labels = {
            'cpf_cnpj': 'CPF/CNPJ',
            'categoria_empresa': 'Categoria',
        }
        widgets = {
            'descricao_curta': forms.TextInput(attrs={'maxlength': 220}),
            'descricao_completa': forms.Textarea(attrs={'rows': 4}),
            'horario_atendimento': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args: object, usuario=None, pode_alterar_status: bool = False, **kwargs: object) -> None:
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'form-control')

        self.fields['nome_fantasia'].required = True
        self.fields['estado'].required = True
        self.fields['cidade'].required = True
        self.fields['cpf_cnpj'].widget.attrs.setdefault('inputmode', 'numeric')
        self.fields['cep'].widget.attrs.setdefault('inputmode', 'numeric')
        self.fields['telefone'].widget.attrs.setdefault('inputmode', 'tel')
        self.fields['whatsapp'].widget.attrs.setdefault('inputmode', 'tel')

        if not pode_alterar_status and self.instance.pk:
            self.fields['status'].disabled = True
            self.fields['status'].help_text = 'Somente proprietários, administradores ou staff podem alterar o status.'
        elif not pode_alterar_status:
            self.fields['status'].choices = [
                (Empresa.Status.RASCUNHO, Empresa.Status.RASCUNHO.label),
                (Empresa.Status.PENDENTE, Empresa.Status.PENDENTE.label),
            ]

    def clean_cpf_cnpj(self) -> str:
        documento = somente_digitos(self.cleaned_data.get('cpf_cnpj', ''))
        tipo = self.cleaned_data.get('tipo_cadastro')

        if tipo in {Empresa.TipoCadastro.AUTONOMO, Empresa.TipoCadastro.INFORMAL}:
            if not documento:
                return ''
            if len(documento) == 11 and not cpf_valido(documento):
                raise forms.ValidationError('CPF inválido.')
            if len(documento) == 14 and not cnpj_valido(documento):
                raise forms.ValidationError('CNPJ inválido.')
            if len(documento) not in {11, 14}:
                raise forms.ValidationError('Informe CPF ou CNPJ válido.')

        if tipo in {Empresa.TipoCadastro.MEI, Empresa.TipoCadastro.EMPRESA}:
            if not documento:
                raise forms.ValidationError('MEI e empresa formal devem informar CNPJ.')
            if len(documento) != 14 or not cnpj_valido(documento):
                raise forms.ValidationError('MEI e empresa formal devem informar CNPJ válido.')

        queryset = Empresa.all_objects.filter(cpf_cnpj=documento, excluido_em__isnull=True)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError('Este documento já está vinculado a outra empresa.')

        return documento

    def clean_logo(self):
        return self._validar_imagem('logo', 2)

    def clean_imagem_capa(self):
        return self._validar_imagem('imagem_capa', 5)

    def _validar_imagem(self, field_name: str, limite_mb: int):
        imagem = self.cleaned_data.get(field_name)
        if not imagem:
            return imagem

        if imagem.size > limite_mb * 1024 * 1024:
            raise forms.ValidationError(f'A imagem deve ter até {limite_mb} MB.')

        content_type = getattr(imagem, 'content_type', '')
        if content_type and content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
            raise forms.ValidationError('Use imagem JPG, PNG ou WEBP.')

        return imagem

    def clean(self) -> dict:
        cleaned_data = super().clean()
        cidade = cleaned_data.get('cidade')
        estado = cleaned_data.get('estado')

        if cidade and estado and cidade.estado_id != estado.id:
            self.add_error('cidade', 'A cidade selecionada não pertence ao estado informado.')

        return cleaned_data


class EmpresaUsuarioForm(forms.ModelForm):
    """Adiciona ou edita colaboradores da empresa."""

    email = forms.EmailField(label='E-mail do usuário')

    class Meta:
        model = EmpresaUsuario
        fields = [
            'email',
            'funcao',
            'administrador',
            'pode_editar',
            'pode_publicar_servico',
            'pode_gerenciar_equipe',
            'ativo',
        ]

    def __init__(self, *args: object, empresa=None, **kwargs: object) -> None:
        self.empresa = empresa
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'form-control')

        if self.instance.pk:
            self.fields['email'].initial = self.instance.usuario.email
            self.fields['email'].disabled = True

    def clean_email(self) -> str:
        email = self.cleaned_data['email'].strip().lower()

        try:
            usuario = Usuario.objects.get(email__iexact=email)
        except Usuario.DoesNotExist as exc:
            raise forms.ValidationError('Nenhum usuário ativo foi encontrado com este e-mail.') from exc

        if not usuario.is_active:
            raise forms.ValidationError('Este usuário está inativo.')

        if self.empresa and not self.instance.pk:
            if EmpresaUsuario.objects.filter(empresa=self.empresa, usuario=usuario).exists():
                raise forms.ValidationError('Este usuário já está vinculado a esta empresa.')

        self.usuario_encontrado = usuario
        return email

    def save(self, commit: bool = True):
        vinculo = super().save(commit=False)
        if self.empresa:
            vinculo.empresa = self.empresa
        if not vinculo.pk:
            vinculo.usuario = self.usuario_encontrado

        if vinculo.funcao == EmpresaUsuario.Funcao.ADMINISTRADOR:
            vinculo.administrador = True
            vinculo.pode_editar = True
            vinculo.pode_publicar_servico = True
            vinculo.pode_gerenciar_equipe = True

        if commit:
            vinculo.save()

        return vinculo


class EmpresaCNPJConsultaForm(forms.Form):
    cnpj = forms.CharField(label='CNPJ', max_length=18)

    def clean_cnpj(self):
        cnpj = somente_digitos(self.cleaned_data['cnpj'])
        if len(cnpj) != 14 or not cnpj_valido(cnpj):
            raise forms.ValidationError('Informe um CNPJ válido.')
        return cnpj


class EmpresaIdentificacaoForm(EmpresaForm):
    class Meta(EmpresaForm.Meta):
        fields = ['tipo_cadastro', 'razao_social', 'nome_fantasia', 'cpf_cnpj', 'inscricao_estadual', 'inscricao_municipal']


class EmpresaApresentacaoForm(EmpresaForm):
    class Meta(EmpresaForm.Meta):
        fields = ['descricao_curta', 'descricao_completa', 'logo', 'imagem_capa']


class EmpresaContatoForm(EmpresaForm):
    class Meta(EmpresaForm.Meta):
        fields = ['telefone', 'whatsapp', 'email', 'site']


class EmpresaEnderecoForm(forms.ModelForm):
    class Meta:
        model = EnderecoCore
        fields = [
            'tipo_endereco',
            'cep',
            'logradouro',
            'numero',
            'complemento',
            'bairro',
            'bairro_texto',
            'cidade',
            'estado',
            'referencia',
            'principal',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class EmpresaCapacidadeForm(forms.ModelForm):
    class Meta:
        model = EmpresaCapacidade
        fields = ['capacidade']


class EmpresaResponsavelForm(forms.ModelForm):
    class Meta:
        model = EmpresaSolicitacao
        fields = ['funcao_pretendida', 'relacao_empresa', 'justificativa']


class EmpresaDocumentoForm(forms.ModelForm):
    class Meta:
        model = PessoaDocumento
        fields = ['tipo_documento', 'numero_normalizado', 'arquivo_frente', 'arquivo_verso', 'arquivo_unico']


class EmpresaSolicitacaoAnaliseForm(forms.ModelForm):
    class Meta:
        model = EmpresaSolicitacao
        fields = ['status', 'motivo_decisao']


class BaseServicoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'form-control')


class ServicoPrestadorForm(BaseServicoForm):
    class Meta:
        model = Servico
        fields = ['prestador_tipo', 'empresa']


class ServicoClassificacaoForm(BaseServicoForm):
    class Meta:
        model = Servico
        fields = ['setor', 'profissao', 'tipo_servico', 'forma_cobranca']


class ServicoApresentacaoForm(BaseServicoForm):
    class Meta:
        model = Servico
        fields = ['titulo', 'descricao_curta', 'descricao_completa', 'experiencia']


class ServicoPrecoForm(BaseServicoForm):
    class Meta:
        model = Servico
        fields = ['preco_inicial', 'preco_final', 'preco_sob_consulta', 'unidade_preco']


class ServicoAtendimentoForm(BaseServicoForm):
    class Meta:
        model = Servico
        fields = ['atendimento_remoto', 'atendimento_presencial', 'atendimento_emergencial', 'prazo_medio']


class ServicoContatoForm(BaseServicoForm):
    class Meta:
        model = Servico
        fields = ['telefone_publico', 'whatsapp_publico', 'email_publico']


class ServicoForm(BaseServicoForm):
    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        if usuario is not None:
            self.fields['empresa'].queryset = (
                empresas_disponiveis_para_usuario(usuario)
                .filter(ativo=True)
                .order_by('nome_fantasia')
            )

    def clean(self):
        cleaned = super().clean()
        if self.usuario and cleaned.get('prestador_tipo'):
            from apps.organizations.plans import validar_contexto_servico
            try:
                validar_contexto_servico(
                    self.usuario,
                    cleaned.get('prestador_tipo'),
                    cleaned.get('empresa'),
                )
            except (ValidationError, PermissionDenied) as exc:
                self.add_error('empresa', str(exc))
        return cleaned

    class Meta:
        model = Servico
        fields = [
            'prestador_tipo',
            'empresa',
            'setor',
            'profissao',
            'tipo_servico',
            'forma_cobranca',
            'titulo',
            'descricao_curta',
            'descricao_completa',
            'experiencia',
            'preco_inicial',
            'preco_final',
            'preco_sob_consulta',
            'unidade_preco',
            'atendimento_remoto',
            'atendimento_presencial',
            'atendimento_emergencial',
            'prazo_medio',
            'telefone_publico',
            'whatsapp_publico',
            'email_publico',
        ]


class ServicoImagemForm(BaseServicoForm):
    class Meta:
        model = ServicoImagem
        fields = ['imagem', 'legenda', 'principal', 'ordem']


class ServicoAreaForm(BaseServicoForm):
    class Meta:
        model = ServicoArea
        fields = ['tipo_area', 'cidade', 'regiao', 'bairro', 'estado', 'raio_km', 'remoto', 'nacional']


class ServicoCaracteristicaForm(BaseServicoForm):
    class Meta:
        model = ServicoCaracteristica
        fields = ['titulo', 'descricao', 'icone', 'ordem', 'ativo']


class ServicoLinkForm(BaseServicoForm):
    class Meta:
        model = ServicoLink
        fields = ['tipo_link', 'titulo', 'url', 'ordem', 'destaque', 'ativo']


class EmpresaLinkForm(BaseServicoForm):
    class Meta:
        model = EmpresaLink
        fields = ['tipo_link', 'titulo', 'url', 'ordem', 'destaque', 'ativo']
