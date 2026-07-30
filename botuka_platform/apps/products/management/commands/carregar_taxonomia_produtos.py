from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.products.models import (
    CategoriaProduto, FamiliaProduto, SegmentoProduto,
    TipoProduto, TipoProdutoSegmento,
)


TAXONOMY = {
    'Tecnologia': {'Celulares': ['Smartphone', 'Celular básico', 'Celular dobrável', 'Acessório para celular'], 'Computadores': ['Notebook', 'Computador desktop', 'Monitor', 'Teclado', 'Mouse'], 'Tablets': ['Tablet'], 'Áudio': ['Fone de ouvido', 'Caixa de som'], 'Vídeo': ['Televisor'], 'Games': ['Console', 'Jogo']},
    'Veículos': {'Carros': ['Automóvel', 'Utilitário', 'Caminhonete'], 'Motos': ['Motocicleta', 'Scooter', 'Ciclomotor'], 'Bicicletas': ['Bicicleta'], 'Peças': ['Peça automotiva'], 'Acessórios automotivos': ['Acessório automotivo']},
    'Moda e acessórios': {'Roupas femininas': ['Roupa feminina'], 'Roupas masculinas': ['Roupa masculina'], 'Roupas infantis': ['Roupa infantil'], 'Calçados': ['Tênis', 'Sapato', 'Sandália', 'Bota'], 'Bolsas': ['Bolsa'], 'Joias e bijuterias': ['Joia', 'Bijuteria']},
    'Casa e decoração': {'Móveis': ['Móvel'], 'Decoração': ['Objeto decorativo'], 'Cama, mesa e banho': ['Roupa de cama'], 'Iluminação': ['Luminária'], 'Utensílios domésticos': ['Utensílio doméstico']},
    'Eletrodomésticos': {'Cozinha': ['Geladeira', 'Fogão', 'Micro-ondas', 'Liquidificador', 'Air fryer'], 'Lavanderia': ['Máquina de lavar'], 'Climatização': ['Ar-condicionado', 'Ventilador'], 'Eletroportáteis': ['Eletroportátil']},
    'Beleza e cuidados pessoais': {'Beleza': ['Cosmético'], 'Cuidados pessoais': ['Produto de higiene']},
    'Alimentos e bebidas': {'Alimentos': ['Alimento'], 'Bebidas': ['Bebida']},
    'Esportes e lazer': {'Equipamentos esportivos': ['Equipamento esportivo'], 'Lazer': ['Artigo de lazer']},
    'Brinquedos': {'Brinquedos': ['Brinquedo']},
    'Livros e papelaria': {'Livros': ['Livro'], 'Papelaria': ['Item de papelaria']},
    'Produtos religiosos': {'Artigos litúrgicos': ['Vela religiosa', 'Incenso', 'Guia', 'Colar religioso'], 'Vestuário religioso': ['Vestuário religioso'], 'Imagens e esculturas': ['Imagem religiosa'], 'Livros religiosos': ['Livro religioso'], 'Instrumentos': ['Instrumento religioso'], 'Objetos ritualísticos': ['Objeto ritualístico']},
    'Artesanato': {'Artesanato geral': ['Peça artesanal']},
    'Pets': {'Alimentação pet': ['Ração'], 'Acessórios pet': ['Acessório para pet']},
    'Construção e ferramentas': {'Ferramentas': ['Ferramenta'], 'Materiais de construção': ['Material de construção']},
    'Saúde e bem-estar': {'Bem-estar': ['Produto de bem-estar'], 'Saúde': ['Produto de saúde']},
    'Serviços': {'Serviços gerais': ['Serviço']},
    'Outros': {'Outros produtos': ['Outro produto']},
}
SEGMENTS = ['Católico', 'Evangélico', 'Espírita', 'Umbanda', 'Candomblé', 'Matriz africana', 'Budista', 'Judaico', 'Islâmico', 'Ecumênico', 'Sem denominação específica']


class Command(BaseCommand):
    help = 'Carrega uma taxonomia comercial idempotente, preservando registros personalizados.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simula a carga e desfaz a transação.')

    def handle(self, *args, **options):
        counters = {'categorias': 0, 'familias': 0, 'tipos': 0, 'segmentos': 0, 'relacoes': 0}
        with transaction.atomic():
            religious_types = []
            for category_order, (category_name, families) in enumerate(TAXONOMY.items(), 1):
                category, created = CategoriaProduto.objects.get_or_create(
                    slug=slugify(category_name),
                    defaults={'nome': category_name, 'ordem': category_order, 'ativo': True},
                )
                counters['categorias'] += int(created)
                for family_order, (family_name, types) in enumerate(families.items(), 1):
                    family, created = FamiliaProduto.objects.get_or_create(
                        categoria=category, slug=slugify(family_name),
                        defaults={'nome': family_name, 'ordem': family_order, 'ativo': True},
                    )
                    counters['familias'] += int(created)
                    for type_order, type_name in enumerate(types, 1):
                        item, created = TipoProduto.objects.get_or_create(
                            familia=family, slug=slugify(type_name),
                            defaults={'nome': type_name, 'ordem': type_order, 'ativo': True, 'permite_segmento': category_name == 'Produtos religiosos'},
                        )
                        counters['tipos'] += int(created)
                        if category_name == 'Produtos religiosos':
                            religious_types.append(item)
            segments = []
            for order, name in enumerate(SEGMENTS, 1):
                segment, created = SegmentoProduto.objects.get_or_create(
                    slug=slugify(name), defaults={'nome': name, 'ordem': order, 'ativo': True},
                )
                counters['segmentos'] += int(created)
                segments.append(segment)
            for item in religious_types:
                if not item.permite_segmento:
                    item.permite_segmento = True
                    item.save(update_fields=['permite_segmento', 'atualizado_em'])
                for order, segment in enumerate(segments, 1):
                    _relation, created = TipoProdutoSegmento.objects.get_or_create(
                        tipo_produto=item, segmento=segment, defaults={'ordem': order, 'ativo': True},
                    )
                    counters['relacoes'] += int(created)
            # Completa categorias legadas sem apagar ou renomear cadastros existentes.
            for category in CategoriaProduto.objects.filter(ativo=True, familias__isnull=True):
                family, created = FamiliaProduto.objects.get_or_create(
                    categoria=category, slug='geral',
                    defaults={'nome': 'Geral', 'ordem': 999, 'ativo': True},
                )
                counters['familias'] += int(created)
                _item, created = TipoProduto.objects.get_or_create(
                    familia=family, slug='produto-geral',
                    defaults={'nome': 'Produto geral', 'ordem': 999, 'ativo': True},
                )
                counters['tipos'] += int(created)
            # Segmentos continuam opcionais; o vínculo apenas os disponibiliza nos tipos religiosos.
            all_segments = list(SegmentoProduto.objects.filter(ativo=True))
            for item in religious_types:
                for order, segment in enumerate(all_segments, 1):
                    _relation, created = TipoProdutoSegmento.objects.get_or_create(
                        tipo_produto=item, segmento=segment,
                        defaults={'ordem': order, 'ativo': True},
                    )
                    counters['relacoes'] += int(created)
            if options['dry_run']:
                transaction.set_rollback(True)
        mode = 'SIMULAÇÃO' if options['dry_run'] else 'CARGA CONCLUÍDA'
        self.stdout.write(self.style.SUCCESS(f'{mode}: {counters}'))
