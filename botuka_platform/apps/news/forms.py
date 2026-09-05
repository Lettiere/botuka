from django import forms
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
from apps.core.services.images import optimize_uploaded_image

from apps.accounts.authorization import pode

from .models import Artigo, ArtigoBloco, Autor, CategoriaNoticia, Coluna, ComentarioArtigo, SerieEditorial, Tag, Tema
from .sanitizers import sanitizar_html_editorial


class ArtigoForm(forms.ModelForm):
    class Meta:
        model = Artigo
        fields = [
            "titulo", "subtitulo", "resumo", "conteudo", "tipo_editorial",
            "categoria", "coluna", "serie", "temas", "tags", "autor_editorial",
            "imagem_capa", "legenda_imagem", "credito_imagem", "fonte_imagem",
            "texto_alternativo_imagem", "fonte", "url_fonte", "data_fato",
            "titulo_seo", "descricao_seo", "imagem_social", "destaque", "urgente",
            "comentarios_permitidos", "comentarios_moderados", "comentarios_encerrados",
        ]
        widgets = {
            "conteudo": forms.Textarea(attrs={"rows": 14, "data-richtext-source": "", "class": "news-richtext-source"}),
            "resumo": forms.Textarea(attrs={"rows": 4, "maxlength": 500}),
            "data_fato": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "temas": forms.SelectMultiple(attrs={"size": 6}),
            "tags": forms.SelectMultiple(attrs={"size": 6}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        self.pode_atribuir_autor = pode(usuario, "news.atribuir_autor")
        self.fields["categoria"].queryset = CategoriaNoticia.objects.filter(ativo=True)
        self.fields["coluna"].queryset = Coluna.objects.filter(ativo=True)
        self.fields["serie"].queryset = SerieEditorial.objects.filter(ativo=True)
        self.fields["temas"].queryset = Tema.objects.filter(ativo=True)
        self.fields["tags"].queryset = Tag.objects.filter(ativo=True)
        self.fields["autor_editorial"].queryset = Autor.objects.filter(ativo=True, usuario__is_active=True)
        if not self.pode_atribuir_autor:
            self.fields.pop("autor_editorial")
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()
        if not self.pode_atribuir_autor and "autor_editorial" in self.data:
            enviado = self.data.get("autor_editorial")
            proprio = Autor.objects.filter(usuario=self.usuario, ativo=True).values_list("pk", flat=True).first()
            if enviado and str(enviado) != str(proprio or ""):
                raise forms.ValidationError("Você não pode atribuir outro autor editorial.")
        return cleaned

    def clean_imagem_capa(self):
        return optimize_uploaded_image(self.cleaned_data.get('imagem_capa'), policy='hero')

    def clean_imagem_social(self):
        return optimize_uploaded_image(self.cleaned_data.get('imagem_social'), policy='hero')

    def clean_conteudo(self):
        conteudo = sanitizar_html_editorial(self.cleaned_data.get("conteudo"))
        if not conteudo:
            raise forms.ValidationError("Informe o conteúdo da notícia.")
        return conteudo


class ArtigoVideoForm(forms.ModelForm):
    class Meta:
        model = ArtigoBloco
        fields = ["titulo", "url", "ordem"]
        widgets = {
            "titulo": forms.TextInput(attrs={
                "placeholder": "T\u00edtulo opcional do v\u00eddeo",
            }),
            "url": forms.URLInput(attrs={
                "placeholder": "https://www.youtube.com/watch?v=...",
            }),
            "ordem": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tipo = ArtigoBloco.Tipo.VIDEO

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.tipo = ArtigoBloco.Tipo.VIDEO

        if commit:
            obj.save()

        return obj


class BaseArtigoVideoFormSet(BaseInlineFormSet):
    def get_queryset(self):
        return super().get_queryset().filter(
            tipo=ArtigoBloco.Tipo.VIDEO
        )


ArtigoVideoFormSet = inlineformset_factory(
    Artigo,
    ArtigoBloco,
    form=ArtigoVideoForm,
    formset=BaseArtigoVideoFormSet,
    fields=["titulo", "url", "ordem"],
    extra=1,
    can_delete=True,
)


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = ComentarioArtigo
        fields = ["texto"]
        widgets = {
            "texto": forms.Textarea(attrs={
                "rows": 3, "maxlength": 1000,
                "placeholder": "Participe da conversa com respeito.",
                "data-comment-text": "",
            }),
        }

    def clean_texto(self):
        texto = (self.cleaned_data.get("texto") or "").strip()
        if not texto:
            raise forms.ValidationError("Escreva um comentário.")
        return texto
