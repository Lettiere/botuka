from django import forms

from apps.organizations.permissions import empresas_disponiveis_para_usuario, usuario_pode_publicar_por_empresa
from .models import (Candidatura, Curso, Curriculo, CurriculoInformacaoAdicional,
                     CurriculoPrivacidade, Experiencia, Formacao, Habilidade,
                     Idioma, Projeto, Vaga)


class VagaForm(forms.ModelForm):
    tipo_responsavel = forms.ChoiceField(
        label='Publicar em nome de',
        choices=(('EMPRESA', 'Empresa'), ('PESSOA_FISICA', 'Pessoa física')),
    )

    class Meta:
        model = Vaga
        fields = [
            'empresa', 'titulo', 'descricao', 'responsabilidades', 'requisitos',
            'beneficios', 'tipo_contrato', 'modalidade', 'jornada', 'quantidade',
            'salario_minimo', 'salario_maximo', 'ocultar_salario', 'cidade',
            'estado', 'bairro', 'endereco_privado', 'visibilidade_localizacao',
            'experiencia', 'escolaridade', 'categoria', 'area_atuacao',
            'inicio', 'encerramento', 'aceita_pcd',
            'aceita_candidatura_simplificada',
        ]
        widgets = {
            'descricao': forms.Textarea(), 'requisitos': forms.Textarea(),
            'responsabilidades': forms.Textarea(), 'beneficios': forms.Textarea(),
            'inicio': forms.DateInput(attrs={'type': 'date'}),
            'encerramento': forms.DateInput(attrs={'type': 'date'}),
            'endereco_privado': forms.TextInput(attrs={'autocomplete': 'street-address'}),
        }
        help_texts = {
            'endereco_privado': 'Nunca será exibido publicamente.',
            'visibilidade_localizacao': 'Controle quais dados de localização serão públicos.',
        }

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        self.fields['tipo_responsavel'].required = False
        self.fields['visibilidade_localizacao'].required = False
        self.fields['visibilidade_localizacao'].initial = Vaga.VisibilidadeLocalizacao.PUBLICA
        self.fields['empresa'].required = False
        tem_empresas = bool(usuario and empresas_disponiveis_para_usuario(usuario).filter(ativo=True).exists())
        if not tem_empresas:
            self.fields['tipo_responsavel'].initial = 'PESSOA_FISICA'
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'form-control')
        self.fields['empresa'].queryset = (
            empresas_disponiveis_para_usuario(usuario).filter(ativo=True)
            if usuario else self.fields['empresa'].queryset.none()
        )
        if self.instance and self.instance.pk:
            self.fields['tipo_responsavel'].initial = (
                'EMPRESA' if self.instance.empresa_id else 'PESSOA_FISICA'
            )

    def clean_empresa(self):
        empresa = self.cleaned_data.get('empresa')
        if empresa and not usuario_pode_publicar_por_empresa(self.usuario, empresa):
            raise forms.ValidationError('Selecione uma empresa que você administra.')
        return empresa

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_responsavel') or (
            'EMPRESA' if cleaned.get('empresa') else 'PESSOA_FISICA'
        )
        cleaned['tipo_responsavel'] = tipo
        empresa = cleaned.get('empresa')
        if tipo == 'EMPRESA' and not empresa:
            self.add_error('empresa', 'Selecione a empresa responsável.')
        if tipo == 'PESSOA_FISICA':
            cleaned['empresa'] = None
            if not self.usuario or not self.usuario.perfil_contratante_completo:
                raise forms.ValidationError(
                    'Para publicar como pessoa física, complete CPF validado, nome, '
                    'contato, cidade, estado, bairro e aceite dos termos. Seus dados '
                    'privados não serão exibidos publicamente.'
                )
            self.instance.empresa = None
            self.instance.perfil_pessoa_fisica = self.usuario
        else:
            self.instance.empresa = empresa
            self.instance.perfil_pessoa_fisica = None
        cleaned['visibilidade_localizacao'] = (
            cleaned.get('visibilidade_localizacao')
            or Vaga.VisibilidadeLocalizacao.PUBLICA
        )
        return cleaned


class CurriculumBaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'form-control')
                if not isinstance(field.widget, (forms.Select, forms.FileInput)):
                    field.widget.attrs.setdefault('placeholder', field.label)


class PerfilProfissionalForm(CurriculumBaseForm):
    class Meta:
        model = Curriculo
        fields = ['titulo_profissional', 'area_profissional', 'objetivo_profissional',
                  'resumo', 'nivel_profissional', 'disponibilidade',
                  'tipo_contratacao_desejada', 'modalidade_preferida',
                  'pretensao_salarial', 'disponivel_viagens', 'disponivel_mudanca']
        labels = {
            'titulo_profissional': 'Título profissional',
            'area_profissional': 'Área profissional',
            'objetivo_profissional': 'Objetivo profissional',
            'resumo': 'Resumo profissional',
            'nivel_profissional': 'Nível profissional',
            'tipo_contratacao_desejada': 'Tipo de contratação desejada',
            'modalidade_preferida': 'Modalidade preferida',
            'pretensao_salarial': 'Pretensão salarial',
            'disponivel_viagens': 'Disponível para viagens',
            'disponivel_mudanca': 'Disponível para mudança',
        }
        help_texts = {
            'resumo': 'Apresente em poucas linhas sua experiência e seus principais diferenciais.',
            'pretensao_salarial': 'Informe apenas números; este dado pode permanecer privado.',
        }
        widgets = {
            'objetivo_profissional': forms.Textarea(attrs={'rows': 3}),
            'resumo': forms.Textarea(attrs={'rows': 5}),
            'pretensao_salarial': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
        }


class ContatoPublicoForm(CurriculumBaseForm):
    class Meta:
        model = Curriculo
        fields = ['telefone_publico', 'email_publico', 'cidade', 'estado',
                  'linkedin', 'portfolio', 'site_profissional', 'github']
        labels = {'telefone_publico': 'Telefone', 'email_publico': 'E-mail'}
        help_texts = {
            'telefone_publico': 'A exibição deste contato é controlada na etapa de privacidade.',
            'email_publico': 'A exibição deste contato é controlada na etapa de privacidade.',
        }
        widgets = {'estado': forms.TextInput(attrs={'maxlength': 2})}


class PublicacaoCurriculoForm(CurriculumBaseForm):
    class Meta:
        model = Curriculo
        fields = ['visibilidade']


class CurriculoPrivacidadeForm(CurriculumBaseForm):
    class Meta:
        model = CurriculoPrivacidade
        fields = ['mostrar_telefone', 'mostrar_email', 'mostrar_cidade',
                  'mostrar_estado', 'mostrar_linkedin', 'mostrar_portfolio',
                  'mostrar_pretensao_salarial']


CurriculoForm = PerfilProfissionalForm


class ExperienciaForm(CurriculumBaseForm):
    class Meta:
        model = Experiencia
        fields = ['titulo', 'cargo', 'tipo_contratacao', 'cidade', 'estado',
                  'inicio', 'fim', 'atual', 'descricao',
                  'resultados_responsabilidades', 'tecnologias_habilidades']
        widgets = {'inicio': forms.DateInput(attrs={'type': 'date'}), 'fim': forms.DateInput(attrs={'type': 'date'})}
        labels = {
            'titulo': 'Empresa',
            'cargo': 'Cargo',
            'atual': 'Trabalho atualmente nesta empresa',
            'resultados_responsabilidades': 'Resultados e responsabilidades',
            'tecnologias_habilidades': 'Tecnologias e habilidades',
        }


class FormacaoForm(CurriculumBaseForm):
    class Meta:
        model = Formacao
        fields = ['instituicao', 'titulo', 'nivel', 'area', 'situacao',
                  'inicio', 'fim', 'concluido', 'descricao']
        widgets = {'inicio': forms.DateInput(attrs={'type': 'date'}), 'fim': forms.DateInput(attrs={'type': 'date'})}
        labels = {'titulo': 'Curso', 'instituicao': 'Instituição', 'concluido': 'Formação concluída'}


class CursoForm(CurriculumBaseForm):
    class Meta:
        model = Curso
        fields = ['tipo', 'titulo', 'instituicao', 'carga_horaria', 'fim',
                  'codigo_credencial', 'url_credencial', 'validade', 'descricao']
        widgets = {'fim': forms.DateInput(attrs={'type': 'date'}), 'validade': forms.DateInput(attrs={'type': 'date'})}
        labels = {
            'titulo': 'Curso ou certificação',
            'instituicao': 'Instituição',
            'carga_horaria': 'Carga horária (horas)',
            'fim': 'Data de conclusão',
            'codigo_credencial': 'Código da credencial',
            'url_credencial': 'URL da credencial',
        }


class HabilidadeForm(CurriculumBaseForm):
    class Meta:
        model = Habilidade
        fields = ['nome', 'categoria', 'nivel', 'anos_experiencia', 'destaque']


class IdiomaForm(CurriculumBaseForm):
    class Meta:
        model = Idioma
        fields = ['nome', 'leitura', 'escrita', 'conversacao', 'nivel']


class ProjetoForm(CurriculumBaseForm):
    class Meta:
        model = Projeto
        fields = ['titulo', 'descricao', 'tipo', 'url', 'imagem',
                  'tecnologias', 'data', 'destaque']
        widgets = {'data': forms.DateInput(attrs={'type': 'date'})}
        labels = {'titulo': 'Projeto', 'url': 'URL do projeto', 'imagem': 'Imagem do projeto'}


class InformacaoAdicionalForm(CurriculumBaseForm):
    class Meta:
        model = CurriculoInformacaoAdicional
        fields = ['possui_cnh', 'categorias_cnh', 'veiculo_proprio',
                  'disponibilidade_horario', 'trabalho_voluntario', 'premiacoes',
                  'interesses_profissionais', 'observacoes']


class CandidaturaForm(forms.ModelForm):
    class Meta: model = Candidatura; fields = ['mensagem']
