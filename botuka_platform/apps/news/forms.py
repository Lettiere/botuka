from django import forms

from apps.accounts.authorization import pode

from .models import Artigo, Autor, CategoriaNoticia, Coluna, SerieEditorial, Tag, Tema


class ArtigoForm(forms.ModelForm):
    class Meta:
        model = Artigo
        fields = [
            "titulo", "subtitulo", "resumo", "conteudo", "tipo_editorial",
            "categoria", "coluna", "serie", "temas", "tags", "autor_editorial",
            "imagem_capa", "credito_imagem", "fonte", "url_fonte", "data_fato",
            "titulo_seo", "descricao_seo", "imagem_social", "destaque", "urgente",
        ]
        widgets = {
            "conteudo": forms.Textarea(attrs={"rows": 14}),
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
