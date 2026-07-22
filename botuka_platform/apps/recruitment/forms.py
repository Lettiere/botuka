from django import forms

from apps.organizations.permissions import empresas_disponiveis_para_usuario, usuario_pode_gerenciar_empresa
from .models import (Candidatura, Curso, Curriculo, CurriculoInformacaoAdicional,
                     CurriculoPrivacidade, Experiencia, Formacao, Habilidade,
                     Idioma, Projeto, Vaga)


class VagaForm(forms.ModelForm):
    class Meta:
        model = Vaga
        exclude = ['usuario_responsavel', 'slug', 'motivo_rejeicao', 'publicado_em', 'ativo', 'excluido_em']
        widgets = {'descricao': forms.Textarea(), 'requisitos': forms.Textarea(), 'responsabilidades': forms.Textarea(), 'beneficios': forms.Textarea(), 'inicio': forms.DateInput(attrs={'type': 'date'}), 'encerramento': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'form-control')
        self.fields['empresa'].queryset = empresas_disponiveis_para_usuario(usuario).filter(ativo=True) if usuario else self.fields['empresa'].queryset.none()

    def clean_empresa(self):
        empresa = self.cleaned_data['empresa']
        if not usuario_pode_gerenciar_empresa(self.usuario, empresa):
            raise forms.ValidationError('Selecione uma empresa que você administra.')
        return empresa


class CurriculumBaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'form-control')


class PerfilProfissionalForm(CurriculumBaseForm):
    class Meta:
        model = Curriculo
        fields = ['titulo_profissional', 'area_profissional', 'objetivo_profissional',
                  'resumo', 'nivel_profissional', 'disponibilidade',
                  'tipo_contratacao_desejada', 'modalidade_preferida',
                  'pretensao_salarial', 'disponivel_viagens', 'disponivel_mudanca']


class ContatoPublicoForm(CurriculumBaseForm):
    class Meta:
        model = Curriculo
        fields = ['telefone_publico', 'email_publico', 'cidade', 'estado',
                  'linkedin', 'portfolio', 'site_profissional', 'github']


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


class FormacaoForm(CurriculumBaseForm):
    class Meta:
        model = Formacao
        fields = ['instituicao', 'titulo', 'nivel', 'area', 'situacao',
                  'inicio', 'fim', 'concluido', 'descricao']
        widgets = {'inicio': forms.DateInput(attrs={'type': 'date'}), 'fim': forms.DateInput(attrs={'type': 'date'})}


class CursoForm(CurriculumBaseForm):
    class Meta:
        model = Curso
        fields = ['tipo', 'titulo', 'instituicao', 'carga_horaria', 'fim',
                  'codigo_credencial', 'url_credencial', 'validade', 'descricao']
        widgets = {'fim': forms.DateInput(attrs={'type': 'date'}), 'validade': forms.DateInput(attrs={'type': 'date'})}


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


class InformacaoAdicionalForm(CurriculumBaseForm):
    class Meta:
        model = CurriculoInformacaoAdicional
        fields = ['possui_cnh', 'categorias_cnh', 'veiculo_proprio',
                  'disponibilidade_horario', 'trabalho_voluntario', 'premiacoes',
                  'interesses_profissionais', 'observacoes']


class CandidaturaForm(forms.ModelForm):
    class Meta: model = Candidatura; fields = ['mensagem']
