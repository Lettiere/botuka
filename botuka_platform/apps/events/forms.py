from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao
from apps.core.services.rich_text import sanitizar_html_rico

from .models import Evento
from .permissions import empresas_para_eventos


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            'titulo', 'resumo', 'descricao', 'imagem_principal', 'imagem_alt',
            'inicio', 'fim', 'local', 'endereco', 'categoria', 'publico',
            'empresa_promotora', 'proprietario', 'responsavel_edicao',
            'organizador', 'realizador', 'permitir_interesse', 'mensagem_interesse',
            'aceita_inscricoes_futuras', 'modalidade_participacao_futura',
            'limite_estimado_publico', 'url_inscricao_externa', 'observacao_ingresso',
        ]
        widgets = {
            'inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fim': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'descricao': forms.Textarea(attrs={
                'rows': 12, 'data-richtext-source': '', 'class': 'richtext-source',
            }),
        }
        labels = {
            'titulo': 'Título do evento', 'resumo': 'Resumo público',
            'descricao': 'Descrição completa', 'imagem_principal': 'Imagem principal',
            'imagem_alt': 'Texto alternativo da imagem', 'inicio': 'Início',
            'fim': 'Término', 'local': 'Nome do local', 'endereco': 'Endereço público',
            'categoria': 'Categoria', 'publico': 'Página pública',
            'empresa_promotora': 'Empresa promotora', 'proprietario': 'Proprietário do registro',
            'responsavel_edicao': 'Responsável pela edição', 'organizador': 'Organizador',
            'realizador': 'Realizador', 'permitir_interesse': 'Permitir demonstração de interesse',
            'mensagem_interesse': 'Mensagem do botão de interesse',
            'aceita_inscricoes_futuras': 'Preparar inscrição futura',
            'modalidade_participacao_futura': 'Modalidade futura de participação',
            'limite_estimado_publico': 'Limite estimado de público',
            'url_inscricao_externa': 'URL externa de inscrição',
            'observacao_ingresso': 'Observação sobre ingresso',
        }
        help_texts = {
            'empresa_promotora': 'Somente empresas dentro do seu vínculo e escopo.',
            'resumo': 'Texto curto usado em listagens, SEO e compartilhamentos.',
            'imagem_alt': 'Descreva objetivamente a imagem para acessibilidade.',
            'mensagem_interesse': 'Se vazio, será usada a mensagem padrão do BOTUKA.',
            'url_inscricao_externa': 'A inscrição externa é independente do botão “Eu vou!”.',
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif not field.widget.attrs.get('class'):
                field.widget.attrs['class'] = 'form-control'
        companies = empresas_para_eventos(user)
        self.fields['empresa_promotora'].queryset = companies
        self.fields['empresa_promotora'].empty_label = 'Evento próprio, sem empresa'
        privileged = usuario_e_master(user) or usuario_tem_permissao(user, 'events.atribuir_responsavel')
        if not privileged:
            self.fields['proprietario'].queryset = get_user_model().objects.filter(pk=user.pk)
            self.fields['responsavel_edicao'].queryset = get_user_model().objects.filter(pk=user.pk)
            self.fields['proprietario'].initial = user
            self.fields['responsavel_edicao'].initial = user
            if self.instance.pk:
                self.fields['proprietario'].disabled = True
                self.fields['responsavel_edicao'].disabled = True
        if companies.count() == 1 and not self.instance.pk:
            self.fields['empresa_promotora'].initial = companies.first()
            self.fields['empresa_promotora'].disabled = True
            self.fields['empresa_promotora'].help_text = 'Sua única empresa autorizada foi selecionada automaticamente.'

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get('empresa_promotora')
        if company and not empresas_para_eventos(self.user).filter(pk=company.pk).exists():
            self.add_error('empresa_promotora', 'Empresa fora do seu escopo autorizado.')
        if not (usuario_e_master(self.user) or usuario_tem_permissao(self.user, 'events.atribuir_responsavel')):
            if cleaned.get('proprietario') != self.user:
                self.add_error('proprietario', 'Você não pode transferir a propriedade do evento.')
            if cleaned.get('responsavel_edicao') != self.user:
                self.add_error('responsavel_edicao', 'Você não pode atribuir outro responsável.')
        return cleaned

    def clean_descricao(self):
        return sanitizar_html_rico(self.cleaned_data.get('descricao'))
