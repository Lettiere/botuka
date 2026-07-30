from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.db.models import Q
from urllib.parse import parse_qs, urlparse

from apps.core.services.rich_text import sanitizar_html_rico
from apps.organizations.permissions import empresas_gerenciaveis_para_usuario

from .models import (
    AtributoProduto,
    CategoriaProduto,
    FamiliaProduto,
    LimiteProdutoAdicional,
    Produto,
    ProdutoImagem,
    ProdutoVideo,
    SegmentoProduto,
    TipoProduto,
    ValorAtributoProduto,
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


def youtube_id(url):
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix('www.')
    if host == 'youtu.be':
        value = parsed.path.strip('/').split('/')[0]
    elif host in {'youtube.com', 'm.youtube.com'}:
        if parsed.path == '/watch':
            value = parse_qs(parsed.query).get('v', [''])[0]
        elif parsed.path.startswith(('/embed/', '/shorts/', '/live/')):
            value = parsed.path.strip('/').split('/')[1]
        else:
            value = ''
    else:
        value = ''
    if not value or len(value) > 20 or not all(char.isalnum() or char in '_-' for char in value):
        raise ValidationError('Informe um link válido do YouTube.')
    return value


class ProdutoForm(forms.ModelForm):
    imagem_principal_upload = forms.ImageField(
        required=False, label='Imagem principal',
        help_text='JPG, PNG ou WebP. Esta será a capa pública do produto.',
    )
    galeria_upload = forms.FileField(
        required=False, label='Galeria de imagens',
        widget=MultipleFileInput(attrs={'multiple': True, 'accept': 'image/jpeg,image/png,image/webp'}),
        help_text='Selecione várias imagens para a galeria.',
    )
    class Meta:
        model = Produto
        exclude = (
            'slug', 'codigo_interno', 'categoria', 'subcategoria', 'video_url',
            'criador_registro', 'proprietario', 'responsavel',
            'aprovado_por', 'publicado_por', 'status', 'motivo_rejeicao',
            'aprovado_em', 'publicado_em', 'ativo', 'removido_em',
        )
        widgets = {
            'descricao_completa': forms.Textarea(attrs={'rows': 12, 'data-richtext-source': '', 'class': 'richtext-source'}),
            'especificacoes': forms.Textarea(attrs={'rows': 8, 'data-richtext-source': '', 'class': 'richtext-source'}),
            'garantia': forms.Textarea(attrs={'rows': 6, 'data-richtext-source': '', 'class': 'richtext-source'}),
        }

    def __init__(self, *args, user, fixed_company=None, **kwargs):
        self.user = user
        self.fixed_company = fixed_company
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif not field.widget.attrs.get('class'):
                field.widget.attrs['class'] = 'form-control'
        step_fields = {
            1: {'nome', 'titular_tipo', 'empresa_proprietaria', 'marca', 'modelo', 'condicao', 'descricao_curta'},
            2: {'setor', 'categoria_taxonomia', 'familia', 'tipo_produto', 'segmento'},
            3: {'preco', 'preco_promocional', 'moeda', 'preco_sob_consulta', 'unidade_venda', 'quantidade_minima', 'estoque_informativo', 'disponibilidade', 'aceita_encomenda', 'prazo_estimado'},
            4: {'descricao_completa', 'especificacoes', 'garantia', 'dimensoes', 'peso', 'cor', 'material', 'tamanho', 'origem', 'fabricante'},
            5: {'whatsapp', 'telefone', 'url_externa', 'destaque', 'publico', 'tags', 'titulo_seo', 'descricao_seo'},
            6: {'imagem_principal_upload', 'galeria_upload', 'imagem_social'},
        }
        for step, names in step_fields.items():
            for name in names & self.fields.keys():
                self.fields[name].widget.attrs['data-step'] = str(step)
                self.fields[name].widget.attrs['data_step'] = str(step)
        self.fields['empresa_proprietaria'].queryset = empresas_gerenciaveis_para_usuario(user).filter(
            ativo=True, status='ATIVA',
        )
        self.fields['empresa_proprietaria'].empty_label = 'Produto próprio (pessoa física)'
        self.fields['titular_tipo'].label = 'Quem está vendendo este produto?'
        self.fields['empresa_proprietaria'].label = 'Empresa vendedora'
        self.fields['empresa_proprietaria'].help_text = 'Escolha produto próprio para vender como pessoa física ou selecione uma empresa autorizada.'
        self.fields['categoria_taxonomia'].label = 'Categoria do produto'
        self.fields['familia'].label = 'Família do produto'
        self.fields['tipo_produto'].label = 'Tipo de produto'
        self.fields['segmento'].label = 'Segmento (quando aplicável)'
        self.fields['categoria_taxonomia'].required = True
        self.fields['familia'].required = True
        self.fields['tipo_produto'].required = True
        saved_category = self.instance.categoria_taxonomia_id
        self.fields['categoria_taxonomia'].queryset = CategoriaProduto.objects.filter(
            Q(ativo=True, removido_em__isnull=True) | Q(pk=saved_category)
        ).distinct().order_by('ordem', 'nome')
        selected_category = self.data.get('categoria_taxonomia') if self.is_bound else self.instance.categoria_taxonomia_id
        selected_family = self.data.get('familia') if self.is_bound else self.instance.familia_id
        selected_type = self.data.get('tipo_produto') if self.is_bound else self.instance.tipo_produto_id
        try:
            self.fields['familia'].queryset = FamiliaProduto.objects.filter(
                Q(ativo=True, removido_em__isnull=True) | Q(pk=self.instance.familia_id),
                categoria_id=selected_category,
            ).distinct().order_by('ordem', 'nome') if selected_category else FamiliaProduto.objects.none()
            self.fields['tipo_produto'].queryset = TipoProduto.objects.filter(
                Q(ativo=True, removido_em__isnull=True) | Q(pk=self.instance.tipo_produto_id),
                familia_id=selected_family,
            ).distinct().order_by('ordem', 'nome') if selected_family else TipoProduto.objects.none()
            self.fields['segmento'].queryset = SegmentoProduto.objects.filter(
            Q(ativo=True, removido_em__isnull=True) | Q(pk=self.instance.segmento_id),
                tipos_relacionados__tipo_produto_id=selected_type,
                tipos_relacionados__ativo=True,
            ).distinct().order_by('ordem', 'nome') if selected_type else SegmentoProduto.objects.none()
        except (TypeError, ValueError):
            self.fields['familia'].queryset = FamiliaProduto.objects.none()
            self.fields['tipo_produto'].queryset = TipoProduto.objects.none()
            self.fields['segmento'].queryset = SegmentoProduto.objects.none()
        if fixed_company:
            self.fields['empresa_proprietaria'].queryset = self.fields['empresa_proprietaria'].queryset.filter(pk=fixed_company.pk)
            self.fields['empresa_proprietaria'].initial = fixed_company
            self.fields['empresa_proprietaria'].disabled = True
            self.fields['titular_tipo'].initial = Produto.TitularTipo.EMPRESA
            self.fields['titular_tipo'].disabled = True
        category_id = self.data.get('categoria_taxonomia') if self.is_bound else getattr(self.instance, 'categoria_taxonomia_id', None)
        try:
            category = CategoriaProduto.objects.filter(pk=category_id, ativo=True).first()
        except (TypeError, ValueError):
            category = None
        self.product_attributes = list(
            AtributoProduto.objects.filter(categoria_taxonomia=category, ativo=True)
        ) if category else []
        existing = {}
        if self.instance.pk:
            existing = {
                item.atributo_id: item.valor
                for item in self.instance.valores_atributos.select_related('atributo')
            }
        for attribute in self.product_attributes:
            field_name = f'atributo_{attribute.pk}'
            options = [(item, item) for item in attribute.opcoes]
            field_class = {
                AtributoProduto.Tipo.INTEIRO: forms.IntegerField,
                AtributoProduto.Tipo.DECIMAL: forms.DecimalField,
                AtributoProduto.Tipo.BOOLEANO: forms.BooleanField,
                AtributoProduto.Tipo.ESCOLHA: forms.ChoiceField,
            }.get(attribute.tipo, forms.CharField)
            field_kwargs = {'label': attribute.nome, 'required': attribute.obrigatorio}
            if attribute.tipo == AtributoProduto.Tipo.ESCOLHA:
                field_kwargs['choices'] = [('', 'Selecione')] + options
            self.fields[field_name] = field_class(**field_kwargs)
            self.fields[field_name].initial = existing.get(attribute.pk)
            if isinstance(self.fields[field_name].widget, forms.CheckboxInput):
                self.fields[field_name].widget.attrs['class'] = 'form-check-input'
            else:
                self.fields[field_name].widget.attrs['class'] = 'form-control'

    def clean(self):
        data = super().clean()
        company = data.get('empresa_proprietaria')
        if company and not empresas_gerenciaveis_para_usuario(self.user).filter(pk=company.pk).exists():
            self.add_error('empresa_proprietaria', 'Empresa fora do seu escopo autorizado.')
        if data.get('titular_tipo') == Produto.TitularTipo.EMPRESA and not company:
            self.add_error('empresa_proprietaria', 'Selecione a empresa proprietária.')
        if data.get('titular_tipo') == Produto.TitularTipo.PESSOA_FISICA and company:
            self.add_error('empresa_proprietaria', 'Um produto pessoal não pode pertencer a empresa.')
        if self.fixed_company and company != self.fixed_company:
            self.add_error('empresa_proprietaria', 'A empresa do contexto não pode ser alterada.')
        for field_name in ('categoria_taxonomia', 'familia', 'tipo_produto', 'segmento'):
            value = data.get(field_name)
            initial_id = getattr(self.instance, f'{field_name}_id', None)
            if value and not value.ativo and value.pk != initial_id:
                self.add_error(field_name, 'Este registro está inativo e não pode ser usado em um novo vínculo.')
        for name in ('descricao_completa', 'especificacoes', 'garantia'):
            data[name] = sanitizar_html_rico(data.get(name))
        category = data.get('categoria_taxonomia')
        family = data.get('familia')
        self.instance.categoria = category.nome if category else self.instance.categoria
        self.instance.subcategoria = family.nome if family else self.instance.subcategoria
        return data

    def clean_galeria_upload(self):
        files = self.files.getlist('galeria_upload')
        if len(files) > 12:
            raise forms.ValidationError('Envie no máximo 12 imagens por vez.')
        for image in files:
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError(f'{image.name}: limite de 5 MB por imagem.')
            if image.content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
                raise forms.ValidationError(f'{image.name}: formato não permitido.')
        return files

    def save_attributes(self, product):
        active_ids = []
        for attribute in self.product_attributes:
            value = self.cleaned_data.get(f'atributo_{attribute.pk}')
            if value in (None, ''):
                continue
            ValorAtributoProduto.objects.update_or_create(
                produto=product, atributo=attribute, defaults={'valor': value},
            )
            active_ids.append(attribute.pk)
        product.valores_atributos.filter(
            atributo__categoria_taxonomia=product.categoria_taxonomia,
        ).exclude(atributo_id__in=active_ids).delete()

    def save_media(self, product):
        main = self.cleaned_data.get('imagem_principal_upload')
        if main:
            product.imagens.filter(ativo=True, removido_em__isnull=True).update(principal=False)
            ProdutoImagem.objects.create(
                produto=product, imagem=main, principal=True,
                texto_alternativo=f'Imagem principal de {product.nome}',
            )
        for order, image in enumerate(self.cleaned_data.get('galeria_upload') or (), start=1):
            ProdutoImagem.objects.create(
                produto=product, imagem=image, ordem=order,
                texto_alternativo=f'{product.nome} — imagem {order}',
            )


class ProdutoImagemForm(forms.ModelForm):
    class Meta:
        model = ProdutoImagem
        fields = ('imagem', 'principal', 'texto_alternativo', 'legenda', 'credito', 'ordem')
        widgets = {'imagem': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif not field.widget.attrs.get('class'):
                field.widget.attrs['class'] = 'form-control'


class LimiteProdutoAdicionalForm(forms.ModelForm):
    class Meta:
        model = LimiteProdutoAdicional
        fields = ('adicional', 'limite_total', 'ilimitado', 'ativo', 'inicio', 'fim', 'motivo')
        widgets = {
            'inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fim': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class ProdutoVideoForm(forms.ModelForm):
    class Meta:
        model = ProdutoVideo
        fields = ('url', 'titulo', 'ordem')
        labels = {'url': 'Link do YouTube', 'titulo': 'Legenda', 'ordem': 'Ordem'}
        widgets = {
            'url': forms.URLInput(attrs={'placeholder': 'https://www.youtube.com/watch?v=...', 'data-video-url': ''}),
            'titulo': forms.TextInput(attrs={'maxlength': 180, 'data-video-caption': ''}),
            'ordem': forms.NumberInput(attrs={'min': 0, 'data-video-order': ''}),
        }

    def clean_url(self):
        value = self.cleaned_data.get('url', '').strip()
        youtube_id(value)
        return value


class BaseProdutoVideoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        ids = set()
        active = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            url = form.cleaned_data.get('url')
            if not url:
                continue
            active += 1
            identifier = youtube_id(url)
            if identifier in ids:
                raise ValidationError('Não repita o mesmo vídeo do YouTube.')
            ids.add(identifier)
        if active > 8:
            raise ValidationError('Informe no máximo oito vídeos ativos.')


ProdutoVideoFormSet = inlineformset_factory(
    Produto, ProdutoVideo, form=ProdutoVideoForm,
    formset=BaseProdutoVideoFormSet, extra=1, can_delete=True, max_num=8, validate_max=True,
)
