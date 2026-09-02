"""Formulários da área interna do usuário."""

from __future__ import annotations

import re

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.core.models import EnderecoCore, PessoaDocumento
from apps.organizations.models import Capacidade, Empresa, EmpresaLink, EmpresaUsuario
from apps.organizations.models import EmpresaCapacidade, EmpresaSolicitacao, UsuarioLimitePersonalizado
from apps.organizations.permissions import empresas_gerenciaveis_para_usuario
from apps.services.models import (
    AreaProfissional,
    Profissao,
    ProfissaoTipoServico,
    Servico,
    ServicoArea,
    ServicoCaracteristica,
    ServicoImagem,
    ServicoLink,
    Setor,
    TipoServico,
)
from apps.core.services.rich_text import sanitizar_html_rico
from apps.core.services.images import optimize_uploaded_image

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
    aceitar_termos_contratante = forms.BooleanField(
        label='Aceito os termos para publicar oportunidades como pessoa física',
        required=False,
        help_text='CPF e endereço serão usados apenas para validação, segurança e responsabilização.',
    )

    class Meta:
        model = Usuario
        fields = [
            'email', 'telefone', 'celular', 'bairro', 'endereco', 'numero',
            'complemento', 'cep', 'visibilidade_localizacao',
        ]
        help_texts = {
            'telefone': 'Telefone para contato.',
            'celular': 'Celular ou WhatsApp pessoal.',
            'endereco': 'Dado privado: nunca será exibido em páginas públicas.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['aceitar_termos_contratante'].widget.attrs['class'] = 'form-check-input'
        self.fields['aceitar_termos_contratante'].initial = bool(
            self.instance and self.instance.termos_contratante_aceitos_em
        )

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get('aceitar_termos_contratante'):
            usuario.termos_contratante_aceitos_em = (
                usuario.termos_contratante_aceitos_em or timezone.now()
            )
        if commit:
            usuario.save()
            self.save_m2m()
        return usuario


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

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if usuario.cpf:
            usuario.cpf_validado_em = timezone.now()
        if commit:
            usuario.save()
            self.save_m2m()
        return usuario


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
            'atuacao',
            'razao_social',
            'nome_fantasia',
            'cpf_cnpj',
            'inscricao_estadual',
            'inscricao_municipal',
            'categoria_empresa',
            'subcategoria_empresa',
            'modalidade_comercial',
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
            'atuacao': 'Atuação',
            'categoria_empresa': 'Categoria',
            'subcategoria_empresa': 'Subcategoria',
            'modalidade_comercial': 'Modalidade comercial',
        }
        widgets = {
            'descricao_curta': forms.TextInput(attrs={'maxlength': 220}),
            'descricao_completa': forms.Textarea(attrs={
                'rows': 12, 'data-richtext-source': '', 'class': 'richtext-source',
            }),
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

        # SUBCATEGORIA ECONOMICA FILTRADA
        subcategoria_field = self.fields.get('subcategoria_empresa')

        if subcategoria_field is not None:
            categoria_id = None

            if self.is_bound:
                categoria_id = self.data.get('categoria_empresa')
            elif self.instance and self.instance.pk:
                categoria_id = self.instance.categoria_empresa_id

            queryset = subcategoria_field.queryset.filter(
                ativo=True,
                removido_em__isnull=True,
            )

            if categoria_id:
                try:
                    categoria_id = int(categoria_id)
                except (TypeError, ValueError):
                    categoria_id = None

            if categoria_id:
                queryset = queryset.filter(
                    categoria_id=categoria_id
                )
            else:
                queryset = queryset.none()

            subcategoria_field.queryset = queryset.order_by(
                'nome'
            )

        self.fields['modalidade_comercial'].required = False
        self.fields['atuacao'].required = True
        self.fields['atuacao'].help_text = (
            'Classifica o negócio, sem conceder capacidades automaticamente.'
        )

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
        imagem = self._validar_imagem('logo', 8)
        return optimize_uploaded_image(imagem, policy='avatar') if imagem else imagem

    def clean_descricao_completa(self) -> str:
        return sanitizar_html_rico(self.cleaned_data.get('descricao_completa', ''))

    def clean_imagem_capa(self):
        imagem = self._validar_imagem('imagem_capa', 8)
        return optimize_uploaded_image(imagem, policy='hero') if imagem else imagem

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

    def clean_subcategoria_empresa(self):
        subcategoria = self.cleaned_data.get(
            'subcategoria_empresa'
        )

        categoria = self.cleaned_data.get(
            'categoria_empresa'
        )

        if subcategoria is None:
            return None

        if categoria is None:
            raise forms.ValidationError(
                'Selecione uma categoria antes da subcategoria.'
            )

        if subcategoria.categoria_id != categoria.id:
            raise forms.ValidationError(
                'A subcategoria selecionada não pertence à categoria informada.'
            )

        return subcategoria

    def clean(self) -> dict:
        cleaned_data = super().clean()
        cidade = cleaned_data.get('cidade')
        estado = cleaned_data.get('estado')

        if cidade and estado and cidade.estado_id != estado.id:
            self.add_error('cidade', 'A cidade selecionada não pertence ao estado informado.')

        return cleaned_data


class EmpresaEtapaForm(EmpresaForm):
    """Recorte persistente do formulário principal para uma etapa do cadastro."""

    CAMPOS_ETAPA = {
        1: ('tipo_cadastro', 'razao_social', 'nome_fantasia', 'cpf_cnpj',
            'inscricao_estadual', 'inscricao_municipal'),
        2: ('atuacao', 'categoria_empresa', 'subcategoria_empresa'),
        3: ('descricao_curta', 'descricao_completa', 'logo', 'imagem_capa'),
        4: ('telefone', 'whatsapp', 'email', 'site'),
        5: ('cep', 'endereco', 'numero', 'complemento', 'bairro', 'estado', 'cidade'),
        6: ('modalidade_comercial', 'atende_online', 'atende_local',
            'horario_atendimento'),
        7: ('perfil_publico',),
    }

    def __init__(self, *args, etapa=1, **kwargs):
        self.etapa = etapa
        super().__init__(*args, **kwargs)
        permitidos = set(self.CAMPOS_ETAPA[etapa])
        for nome in list(self.fields):
            if nome not in permitidos:
                self.fields.pop(nome)

        if etapa < 7:
            for nome in self.fields:
                self.fields[nome].required = nome in {
                    'nome_fantasia', 'atuacao', 'estado', 'cidade'
                }

        atuacao = self.instance.atuacao if self.instance else None
        if etapa == 6 and atuacao == Empresa.Atuacao.SERVICOS:
            self.fields.pop('modalidade_comercial', None)
        elif etapa == 6 and 'modalidade_comercial' in self.fields:
            self.fields['modalidade_comercial'].required = True

    def clean(self):
        cleaned_data = super().clean()
        atuacao = self.instance.atuacao if self.instance else None
        if atuacao == Empresa.Atuacao.SERVICOS:
            cleaned_data['modalidade_comercial'] = ''
            self.instance.modalidade_comercial = ''
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

    def __init__(self, *args: object, empresa=None, ator=None, **kwargs: object) -> None:
        self.empresa = empresa
        self.ator = ator
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'form-control')

        if self.instance.pk:
            self.fields['email'].initial = self.instance.usuario.email
            self.fields['email'].disabled = True

        from apps.accounts.permissions import usuario_e_master
        if not usuario_e_master(self.ator):
            bloqueados = {EmpresaUsuario.Funcao.ADMINISTRADOR_INSTITUCIONAL}
            self.fields['funcao'].choices = [
                choice for choice in self.fields['funcao'].choices
                if choice[0] not in bloqueados
            ]

    def clean_funcao(self):
        from apps.accounts.permissions import usuario_e_master
        funcao = self.cleaned_data['funcao']
        if (
            funcao == EmpresaUsuario.Funcao.ADMINISTRADOR_INSTITUCIONAL
            and not usuario_e_master(self.ator)
        ):
            raise forms.ValidationError('Somente MASTER pode atribuir este papel.')
        return funcao

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


class EmpresaInstitucionalForm(forms.ModelForm):
    """Campos críticos, usados apenas pela tela autorizada da plataforma."""

    class Meta:
        model = Empresa
        fields = (
            'tipo_organizacao', 'status_institucional', 'institucional',
            'oficial', 'parceira_oficial', 'selo_oficial',
            'verificada_institucionalmente', 'observacao_institucional',
        )
        widgets = {'observacao_institucional': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'
            field.widget.attrs.setdefault('class', css)


class UsuarioLimitePersonalizadoForm(forms.ModelForm):
    class Meta:
        model = UsuarioLimitePersonalizado
        fields = (
            'empresas_ilimitadas', 'servicos_ilimitados',
            'limite_empresas', 'limite_servicos', 'inicio', 'fim',
            'motivo', 'observacoes', 'ativo',
        )
        widgets = {
            'inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'fim': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'observacoes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inicio'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['fim'].input_formats = ('%Y-%m-%dT%H:%M',)
        for field in self.fields.values():
            css = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'
            field.widget.attrs.setdefault('class', css)


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

    def __init__(self, *args, empresa=None, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)
        queryset = Capacidade.objects.filter(ativo=True).order_by('nome')
        if empresa is not None:
            elegiveis = [
                capacidade.pk
                for capacidade in queryset
                if empresa.pode_solicitar_capacidade(capacidade.codigo)
            ]
            existentes = empresa.capacidades_empresa.values_list(
                'capacidade_id', flat=True,
            )
            queryset = queryset.filter(pk__in=elegiveis).exclude(pk__in=existentes)
        self.fields['capacidade'].queryset = queryset

    def clean_capacidade(self):
        capacidade = self.cleaned_data['capacidade']
        if (
            self.empresa is not None
            and not self.empresa.pode_solicitar_capacidade(capacidade.codigo)
        ):
            raise forms.ValidationError(
                'Esta capacidade não é compatível com a atuação da empresa.'
            )
        return capacidade


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
        fields = ['setor', 'area', 'profissao', 'tipo_servico', 'forma_cobranca']


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


class ServicoRapidoForm(BaseServicoForm):
    class Meta:
        model = Servico
        fields = [
            'prestador_tipo', 'empresa', 'titulo', 'setor', 'descricao_curta',
            'preco_inicial', 'preco_sob_consulta', 'atendimento_presencial',
            'atendimento_remoto',
        ]
        labels = {
            'prestador_tipo': 'Tipo de prestador',
            'empresa': 'Empresa responsável',
            'titulo': 'Nome do serviço',
            'setor': 'Categoria do serviço',
            'descricao_curta': 'Descrição curta',
            'preco_inicial': 'Preço inicial',
            'preco_sob_consulta': 'Preço sob consulta',
            'atendimento_presencial': 'Presencial',
            'atendimento_remoto': 'Online',
        }
        widgets = {'descricao_curta': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, usuario=None, empresa_contexto=None, **kwargs):
        self.usuario = usuario
        self.empresa_contexto = empresa_contexto
        super().__init__(*args, **kwargs)
        self.fields['setor'].queryset = Setor.objects.visiveis_para(usuario).filter(ativo=True).order_by('nome')
        self.fields['empresa'].queryset = empresas_gerenciaveis_para_usuario(usuario).filter(
            ativo=True,
            atuacao__in=(
                Empresa.Atuacao.SERVICOS,
                Empresa.Atuacao.COMERCIO_E_SERVICOS,
            ),
        ).order_by('nome_fantasia') if usuario is not None else Empresa.objects.none()
        for nome in ('titulo', 'setor', 'descricao_curta'):
            self.fields[nome].required = True
        if empresa_contexto is not None:
            self.fields['empresa'].queryset = self.fields['empresa'].queryset.filter(
                pk=empresa_contexto.pk,
            )
            self.fields['empresa'].initial = empresa_contexto
            self.fields['empresa'].disabled = True
            self.fields['prestador_tipo'].initial = Servico.PrestadorTipo.EMPRESA
            self.fields['prestador_tipo'].disabled = True

    def clean(self):
        cleaned = super().clean()
        prestador_tipo = cleaned.get('prestador_tipo')
        empresa = cleaned.get('empresa')
        preco = cleaned.get('preco_inicial')
        sob_consulta = cleaned.get('preco_sob_consulta')

        if preco is not None and preco < 0:
            self.add_error('preco_inicial', 'O preço não pode ser negativo.')
        if sob_consulta and preco is not None:
            self.add_error(
                'preco_inicial',
                'Remova o preço informado ou desmarque “Preço sob consulta”.',
            )
        if not sob_consulta and preco is None:
            self.add_error(
                'preco_inicial',
                'Informe um preço inicial ou marque “Preço sob consulta”.',
            )
        if not cleaned.get('atendimento_presencial') and not cleaned.get('atendimento_remoto'):
            raise forms.ValidationError('Selecione atendimento presencial, online ou ambos.')

        if prestador_tipo == Servico.PrestadorTipo.PESSOA_FISICA:
            if empresa is not None:
                self.add_error('empresa', 'O prestador autônomo não pode usar uma empresa.')
            cleaned['empresa'] = None
        elif prestador_tipo == Servico.PrestadorTipo.EMPRESA:
            if empresa is None:
                self.add_error('empresa', 'Informe a empresa prestadora.')
            elif not empresa.pode_criar_rascunho_servico:
                self.add_error(
                    'empresa',
                    'A atuação desta empresa não permite cadastrar serviços.',
                )
        if self.usuario is not None and prestador_tipo:
            from apps.organizations.plans import validar_contexto_servico
            try:
                validar_contexto_servico(self.usuario, prestador_tipo, cleaned.get('empresa'))
            except (ValidationError, PermissionDenied) as exc:
                self.add_error('empresa', str(exc))
        return cleaned

    def save(self, commit=True):
        servico = super().save(commit=False)
        servico.usuario_responsavel = self.usuario
        if servico.prestador_tipo == Servico.PrestadorTipo.PESSOA_FISICA:
            servico.empresa = None
        if commit:
            servico.save()
        return servico

class ServicoForm(BaseServicoForm):
    def __init__(
        self,
        *args,
        usuario=None,
        empresa_contexto=None,
        acao=None,
        **kwargs,
    ):
        self.usuario = usuario
        self.empresa_contexto = empresa_contexto
        self.acao = acao
        super().__init__(*args, **kwargs)

        self.fields['area'].queryset = AreaProfissional.objects.none()
        self.fields['profissao'].queryset = Profissao.objects.none()
        self.fields['tipo_servico'].queryset = TipoServico.objects.none()
        self.fields['setor'].queryset = Setor.objects.visiveis_para(usuario).filter(ativo=True).order_by('nome')

        acao_efetiva = self.acao
        if acao_efetiva is None and self.is_bound:
            acao_efetiva = self.data.get('acao')

        exige_campos_completos = bool(
            acao_efetiva == 'publicar'
            or (
                self.instance
                and self.instance.pk
                and self.instance.status != Servico.Status.RASCUNHO
            )
        )

        for nome in ('setor', 'area', 'profissao', 'forma_cobranca', 'titulo'):
            self.fields[nome].required = exige_campos_completos

        self.fields['tipo_servico'].required = False
        self.fields['tipo_servico'].label = 'Tipo de serviço (opcional)'
        self.fields['area'].empty_label = 'Selecione primeiro o setor'
        self.fields['profissao'].empty_label = 'Selecione primeiro a área'
        self.fields['tipo_servico'].empty_label = 'Selecione primeiro a profissão'
        self.fields['empresa'].empty_label = 'Selecione uma empresa'

        setor_id = None
        area_id = None
        profissao_id = None

        if self.is_bound:
            setor_id = self.data.get('setor')
            area_id = self.data.get('area')
            profissao_id = self.data.get('profissao')
        elif self.instance and self.instance.pk:
            setor_id = self.instance.setor_id
            area_id = self.instance.area_id
            profissao_id = self.instance.profissao_id

        if setor_id and str(setor_id).isdigit():
            self.fields['area'].queryset = (
                AreaProfissional.objects.visiveis_para(usuario)
                .filter(setor_id=setor_id, ativo=True)
                .order_by('nome')
            )

        if area_id and str(area_id).isdigit() and setor_id and str(setor_id).isdigit():
            self.fields['profissao'].queryset = (
                Profissao.objects.visiveis_para(usuario)
                .filter(area_id=area_id, setor_id=setor_id, ativo=True)
                .order_by('nome')
            )

        if profissao_id and str(profissao_id).isdigit():
            vinculo_filter = Q(
                ativo=True,
                vinculos_profissoes__profissao_id=profissao_id,
                vinculos_profissoes__ativo=True,
                vinculos_profissoes__in=ProfissaoTipoServico.objects.visiveis_para(usuario),
            )
            if self.instance and self.instance.pk and self.instance.tipo_servico_id:
                vinculo_filter |= Q(pk=self.instance.tipo_servico_id)
            self.fields['tipo_servico'].queryset = (
                TipoServico.objects.visiveis_para(usuario).filter(
                    vinculo_filter,
                ).distinct().order_by('nome')
            )

        if usuario is not None:
            empresa_atual_id = (
                self.instance.empresa_id
                if self.instance and self.instance.pk
                else None
            )
            filtro_empresas = Q(
                ativo=True,
                atuacao__in=(
                    Empresa.Atuacao.SERVICOS,
                    Empresa.Atuacao.COMERCIO_E_SERVICOS,
                ),
            )
            if empresa_atual_id:
                filtro_empresas |= Q(pk=empresa_atual_id)
            empresas_permitidas = (
                empresas_gerenciaveis_para_usuario(usuario)
                .filter(filtro_empresas)
                .order_by('nome_fantasia')
            )

            if empresa_contexto is not None:
                empresas_permitidas = empresas_permitidas.filter(
                    pk=empresa_contexto.pk
                )

                self.fields['empresa'].initial = empresa_contexto
                self.fields['empresa'].disabled = True

                self.fields['prestador_tipo'].initial = (
                    Servico.PrestadorTipo.EMPRESA
                )
                self.fields['prestador_tipo'].disabled = True

            self.fields['empresa'].queryset = empresas_permitidas

    def clean(self):
        cleaned = super().clean()
        prestador_tipo = cleaned.get('prestador_tipo')
        empresa = cleaned.get('empresa')
        setor = cleaned.get('setor')
        area = cleaned.get('area')
        profissao = cleaned.get('profissao')
        tipo_servico = cleaned.get('tipo_servico')

        # O queryset dependente rejeita corretamente IDs de outro setor antes
        # de clean(); preserve também a mensagem de domínio útil ao usuário.
        area_enviada = self.data.get('area') if self.is_bound else None
        if setor and not area and area_enviada and str(area_enviada).isdigit():
            if AreaProfissional.objects.filter(pk=area_enviada).exclude(setor=setor).exists():
                self.add_error('area', 'A área profissional não pertence ao setor selecionado.')
        profissao_enviada = self.data.get('profissao') if self.is_bound else None
        if area and not profissao and profissao_enviada and str(profissao_enviada).isdigit():
            if Profissao.objects.filter(pk=profissao_enviada).exclude(area=area).exists():
                self.add_error('profissao', 'A profissão não pertence à área profissional selecionada.')

        if prestador_tipo == Servico.PrestadorTipo.PESSOA_FISICA:
            if empresa is not None:
                self.add_error('empresa', 'O prestador autônomo é sempre o usuário autenticado; não envie uma empresa.')
            cleaned['empresa'] = None
        elif (
            prestador_tipo == Servico.PrestadorTipo.EMPRESA
            and empresa is not None
            and not empresa.pode_criar_rascunho_servico
            and not (
                self.instance
                and self.instance.pk
                and self.instance.empresa_id == empresa.pk
            )
        ):
            self.add_error(
                'empresa',
                'A atuação desta empresa não permite cadastrar serviços.',
            )

        if area and setor and area.setor_id != setor.pk:
            self.add_error('area', 'A área profissional não pertence ao setor selecionado.')
        if profissao and setor and profissao.setor_id != setor.pk:
            self.add_error('profissao', 'A profissão não pertence ao setor selecionado.')
        if profissao and not area:
            self.add_error('profissao', 'Selecione a área profissional da profissão.')
        if profissao and profissao.area_id and area and profissao.area_id != area.pk:
            self.add_error('profissao', 'A profissão não pertence à área profissional selecionada.')
        tipo_enviado = self.data.get('tipo_servico') if self.is_bound else None
        if profissao and not tipo_servico and tipo_enviado and str(tipo_enviado).isdigit():
            if TipoServico.objects.filter(pk=tipo_enviado).exists():
                self.add_error('tipo_servico', 'O tipo de serviço não pertence à profissão selecionada.')
        if (
            profissao and tipo_servico and profissao.area_id
            and ProfissaoTipoServico.objects.visiveis_para(self.usuario).filter(
                profissao=profissao, ativo=True,
            ).exists()
            and not ProfissaoTipoServico.objects.visiveis_para(self.usuario).filter(
                profissao=profissao,
                tipo_servico=tipo_servico,
                ativo=True,
                tipo_servico__ativo=True,
            ).exists()
        ):
            self.add_error('tipo_servico', 'O tipo de serviço não pertence à profissão selecionada.')

        if self.usuario and prestador_tipo:
            from apps.organizations.plans import validar_contexto_servico
            try:
                validar_contexto_servico(
                    self.usuario,
                    prestador_tipo,
                    cleaned.get('empresa'),
                )
            except (ValidationError, PermissionDenied) as exc:
                self.add_error('empresa', str(exc))
        return cleaned

    def save(self, commit=True):
        servico = super().save(commit=False)
        if self.usuario is not None and not servico.pk:
            servico.usuario_responsavel = self.usuario
        if servico.prestador_tipo == Servico.PrestadorTipo.PESSOA_FISICA:
            servico.empresa = None
        if commit:
            servico.save()
            self.save_m2m()
        return servico

    def clean_descricao_completa(self):
        return sanitizar_html_rico(self.cleaned_data.get('descricao_completa'))

    def clean_experiencia(self):
        return sanitizar_html_rico(self.cleaned_data.get('experiencia'))

    class Meta:
        model = Servico
        fields = [
            'prestador_tipo',
            'empresa',
            'setor',
            'area',
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
        labels = {
            'prestador_tipo': 'Tipo de prestador',
            'empresa': 'Empresa responsável',
            'setor': 'Setor',
            'area': 'Área profissional',
            'profissao': 'Profissão',
            'tipo_servico': 'Tipo de serviço',
            'forma_cobranca': 'Forma de cobrança',
            'titulo': 'Título do serviço',
            'descricao_curta': 'Resumo',
            'descricao_completa': 'Descrição completa',
            'experiencia': 'Experiência e qualificações',
            'preco_inicial': 'Preço inicial',
            'preco_final': 'Preço final',
            'preco_sob_consulta': 'Preço sob consulta',
            'unidade_preco': 'Unidade de preço',
            'atendimento_remoto': 'Atendimento remoto',
            'atendimento_presencial': 'Atendimento presencial',
            'atendimento_emergencial': 'Atendimento emergencial',
            'prazo_medio': 'Prazo médio',
            'telefone_publico': 'Telefone público',
            'whatsapp_publico': 'WhatsApp público',
            'email_publico': 'E-mail público',
        }
        help_texts = {
            'empresa': 'São listadas apenas empresas que você administra.',
            'area': 'As opções são carregadas de acordo com o setor.',
            'profissao': 'As opções são carregadas de acordo com a área profissional.',
            'tipo_servico': 'As opções são carregadas de acordo com a profissão.',
        }
        widgets = {
            'descricao_completa': forms.Textarea(attrs={
                'rows': 12, 'data-richtext-source': '',
                'class': 'richtext-source',
            }),
            'experiencia': forms.Textarea(attrs={'rows': 5}),
        }


class ServicoImagemForm(BaseServicoForm):
    class Meta:
        model = ServicoImagem
        fields = ['imagem', 'legenda', 'credito', 'texto_alternativo', 'principal', 'ordem']


class ServicoAreaForm(BaseServicoForm):
    def __init__(self, *args, empresa_contexto=None, **kwargs):
        self.empresa_contexto = empresa_contexto
        super().__init__(*args, **kwargs)

        if not self.is_bound and empresa_contexto is not None:
            from apps.core.models import EstadoBrasil, CidadeBrasil

            estado = getattr(empresa_contexto, 'estado', None)
            cidade = getattr(empresa_contexto, 'cidade', None)

            if estado:
                estado_core = EstadoBrasil.objects.filter(
                    sigla__iexact=estado.sigla,
                    ativo=True,
                ).first()

                if estado_core:
                    self.fields['estado'].initial = estado_core

            if cidade:
                cidade_core = CidadeBrasil.objects.filter(
                    codigo_ibge=cidade.codigo_ibge,
                    ativo=True,
                ).first()

                if cidade_core:
                    self.fields['cidade'].initial = cidade_core

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
