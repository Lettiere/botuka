from django import forms
from .models import CategoriaProduto, FamiliaProduto, SegmentoProduto, TipoProduto

class StyledForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control')

class CategoriaProdutoGestaoForm(StyledForm):
    class Meta:
        model = CategoriaProduto
        fields = ['nome','slug','descricao','icone','ordem','ativo']

class FamiliaProdutoGestaoForm(StyledForm):
    class Meta:
        model = FamiliaProduto
        fields = ['categoria','nome','slug','descricao','ordem','ativo']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if not self.instance.pk:
            self.fields['categoria'].queryset = CategoriaProduto.objects.filter(ativo=True, removido_em__isnull=True)

class TipoProdutoGestaoForm(StyledForm):
    segmentos_permitidos = forms.ModelMultipleChoiceField(
        queryset=SegmentoProduto.objects.filter(ativo=True, removido_em__isnull=True),
        required=False, widget=forms.CheckboxSelectMultiple,
    )
    class Meta:
        model = TipoProduto
        fields = ['familia','nome','slug','descricao','ordem','ativo','permite_segmento','exige_segmento']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if not self.instance.pk:
            self.fields['familia'].queryset = FamiliaProduto.objects.filter(ativo=True, removido_em__isnull=True, categoria__ativo=True)
        if self.instance.pk:
            self.fields['segmentos_permitidos'].initial = self.instance.segmentos.filter(tipos_relacionados__ativo=True)
    def clean(self):
        data=super().clean()
        if data.get('exige_segmento') and not data.get('permite_segmento'):
            self.add_error('exige_segmento','Ative “permite segmento” antes de torná-lo obrigatório.')
        if not data.get('permite_segmento') and data.get('segmentos_permitidos'):
            self.add_error('segmentos_permitidos','Este tipo não permite segmentos.')
        return data
    def save(self,commit=True):
        item=super().save(commit)
        if commit:
            selected=self.cleaned_data.get('segmentos_permitidos',())
            ids=set(selected.values_list('pk',flat=True))
            item.segmentos_relacionados.exclude(segmento_id__in=ids).update(ativo=False)
            for segment in selected:
                rel,_=item.segmentos_relacionados.get_or_create(segmento=segment)
                if not rel.ativo:
                    rel.ativo=True
                    rel.save(update_fields=['ativo','atualizado_em'])
        return item

class SegmentoProdutoGestaoForm(StyledForm):
    class Meta:
        model = SegmentoProduto
        fields = ['nome','slug','descricao','ordem','ativo']
