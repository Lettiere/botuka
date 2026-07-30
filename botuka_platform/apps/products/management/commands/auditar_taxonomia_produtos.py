from django.core.management.base import BaseCommand
from django.db.models import Count, F, Q

from apps.products.models import (
    CategoriaProduto, FamiliaProduto, Produto, SegmentoProduto,
    TipoProduto, TipoProdutoSegmento,
)


class Command(BaseCommand):
    help = 'Audita a taxonomia de produtos sem alterar dados.'

    def add_arguments(self, parser):
        parser.add_argument('--detalhado', action='store_true', help='Lista UUID e nome dos registros inconsistentes.')

    def handle(self, *args, **options):
        detailed = options['detalhado']
        groups = {
            'Produtos sem classificação': {
                'Sem categoria': Produto.objects.filter(categoria_taxonomia__isnull=True),
                'Sem família': Produto.objects.filter(familia__isnull=True),
                'Sem tipo': Produto.objects.filter(tipo_produto__isnull=True),
            },
            'Produtos com classificação incompatível': {
                'Família incompatível': Produto.objects.filter(familia__isnull=False).exclude(familia__categoria_id=F('categoria_taxonomia_id')),
                'Tipo incompatível': Produto.objects.filter(tipo_produto__isnull=False).exclude(tipo_produto__familia_id=F('familia_id')),
                'Segmento incompatível': Produto.objects.filter(segmento__isnull=False).exclude(
                    tipo_produto__segmentos_relacionados__segmento_id=F('segmento_id'),
                    tipo_produto__segmentos_relacionados__ativo=True,
                ),
            },
            'Taxonomias inativas em uso': {
                'Produtos com taxonomia inativa': Produto.objects.filter(
                    Q(categoria_taxonomia__ativo=False) | Q(familia__ativo=False)
                    | Q(tipo_produto__ativo=False) | Q(segmento__ativo=False)
                ),
            },
            'Registros órfãos': {
                'Categorias sem famílias': CategoriaProduto.objects.annotate(total=Count('familias')).filter(total=0),
                'Famílias sem tipos': FamiliaProduto.objects.annotate(total=Count('tipos')).filter(total=0),
                'Tipos que exigem segmento sem vínculo': TipoProduto.objects.filter(exige_segmento=True).annotate(
                    total=Count('segmentos_relacionados', filter=Q(segmentos_relacionados__ativo=True))
                ).filter(total=0),
                'Segmentos sem vínculo': SegmentoProduto.objects.annotate(total=Count('tipos_relacionados')).filter(total=0),
            },
        }
        self.stdout.write(self.style.MIGRATE_HEADING('AUDITORIA DE TAXONOMIA DE PRODUTOS — SOMENTE LEITURA'))
        for label, model in (
            ('Categorias', CategoriaProduto), ('Famílias', FamiliaProduto),
            ('Tipos', TipoProduto), ('Segmentos', SegmentoProduto),
        ):
            self.stdout.write(f'\n{label}\n  Total: {model.objects.count()} | Ativos: {model.objects.filter(ativo=True).count()}')
        for heading, checks in groups.items():
            self.stdout.write(f'\n{heading}')
            for label, queryset in checks.items():
                queryset = queryset.distinct()
                self.stdout.write(f'  {label}: {queryset.count()}')
                if detailed:
                    for item in queryset[:100]:
                        self.stdout.write(f'    - {item.uuid} | {item}')
        self.stdout.write('\nDuplicidades')
        scopes = [
            ('Categorias', CategoriaProduto, ('slug',)),
            ('Famílias', FamiliaProduto, ('categoria_id', 'slug')),
            ('Tipos', TipoProduto, ('familia_id', 'slug')),
            ('Segmentos', SegmentoProduto, ('slug',)),
            ('Relações tipo/segmento', TipoProdutoSegmento, ('tipo_produto_id', 'segmento_id')),
        ]
        for label, model, fields in scopes:
            total = model.objects.values(*fields).annotate(n=Count('id')).filter(n__gt=1).count()
            self.stdout.write(f'  {label}: {total}')
