from django.db import migrations
from django.utils.text import slugify


CATEGORIES = {
    'Tecnologia': {
        'Celulares': ['Smartphone', 'Celular básico', 'Celular dobrável', 'Acessório para celular'],
        'Computadores': ['Notebook', 'Computador desktop', 'Tablet', 'Monitor'],
        'Acessórios': ['Cabo', 'Carregador', 'Periférico'],
        'Áudio e vídeo': ['Fone de ouvido', 'Caixa de som', 'Televisor'],
    },
    'Veículos': {'Carros': ['Automóvel', 'Utilitário', 'Caminhonete'], 'Motos': ['Motocicleta', 'Scooter', 'Ciclomotor'], 'Peças': ['Peça automotiva'], 'Acessórios': ['Acessório automotivo']},
    'Moda': {'Roupas': ['Camiseta', 'Camisa', 'Calça', 'Vestido', 'Casaco'], 'Calçados': ['Tênis', 'Sapato', 'Sandália', 'Bota'], 'Bolsas': ['Bolsa'], 'Acessórios': ['Acessório de moda']},
    'Casa e decoração': {'Móveis': ['Móvel'], 'Utensílios': ['Utensílio doméstico'], 'Decoração': ['Objeto decorativo'], 'Iluminação': ['Luminária']},
    'Eletrodomésticos': {'Geladeiras': ['Geladeira'], 'Fogões': ['Fogão'], 'Máquinas de lavar': ['Máquina de lavar'], 'Eletroportáteis': ['Eletroportátil']},
    'Beleza e cuidados pessoais': {'Beleza': ['Cosmético'], 'Cuidados pessoais': ['Produto de higiene']},
    'Alimentos e bebidas': {'Alimentos': ['Alimento'], 'Bebidas': ['Bebida']},
    'Esportes': {'Equipamentos esportivos': ['Equipamento esportivo']},
    'Brinquedos': {'Brinquedos': ['Brinquedo']},
    'Livros e papelaria': {'Livros': ['Livro'], 'Papelaria': ['Item de papelaria']},
    'Produtos religiosos': {
        'Artigos litúrgicos': ['Vela', 'Incenso', 'Imagem religiosa', 'Guia', 'Colar religioso', 'Objeto ritualístico'],
        'Vestuário religioso': ['Vestuário religioso'], 'Imagens e esculturas': ['Imagem ou escultura'],
        'Instrumentos': ['Instrumento religioso'], 'Decoração religiosa': ['Decoração religiosa'],
        'Livros religiosos': ['Livro religioso'],
    },
    'Serviços': {'Serviços gerais': ['Serviço']},
    'Outros': {'Outros produtos': ['Outro produto']},
}

SEGMENTS = ['Católico', 'Evangélico', 'Espírita', 'Umbanda', 'Candomblé', 'Tradições de matriz africana', 'Budista', 'Judaico', 'Islâmico', 'Ecumênico', 'Sem denominação específica']

PERMISSIONS = [
    ('products.taxonomy.visualizar', 'Visualizar taxonomias'),
    *[(f'products.taxonomy.{entity}.{action}', f'{action.title()} {entity}')
      for entity in ('categoria', 'familia', 'tipo', 'segmento')
      for action in ('criar', 'editar', 'desativar')],
]


def seed(apps, schema_editor):
    Category = apps.get_model('products', 'CategoriaProduto')
    Family = apps.get_model('products', 'FamiliaProduto')
    Type = apps.get_model('products', 'TipoProduto')
    Segment = apps.get_model('products', 'SegmentoProduto')
    Relation = apps.get_model('products', 'TipoProdutoSegmento')
    Permission = apps.get_model('core', 'Permissao')
    religious_types = []
    for category_order, (category_name, families) in enumerate(CATEGORIES.items(), 1):
        category, _ = Category.objects.get_or_create(
            slug=slugify(category_name), defaults={'nome': category_name, 'ordem': category_order, 'ativo': True},
        )
        for family_order, (family_name, types) in enumerate(families.items(), 1):
            family, _ = Family.objects.get_or_create(
                categoria=category, slug=slugify(family_name),
                defaults={'nome': family_name, 'ordem': family_order, 'ativo': True},
            )
            for type_order, type_name in enumerate(types, 1):
                item, _ = Type.objects.get_or_create(
                    familia=family, slug=slugify(type_name),
                    defaults={
                        'nome': type_name, 'ordem': type_order, 'ativo': True,
                        'permite_segmento': category_name == 'Produtos religiosos',
                    },
                )
                if category_name == 'Produtos religiosos':
                    religious_types.append(item)
    segments = []
    for order, name in enumerate(SEGMENTS, 1):
        segment, _ = Segment.objects.get_or_create(
            slug=slugify(name), defaults={'nome': name, 'ordem': order, 'ativo': True},
        )
        segments.append(segment)
    for item in religious_types:
        for order, segment in enumerate(segments, 1):
            Relation.objects.get_or_create(tipo_produto=item, segmento=segment, defaults={'ordem': order, 'ativo': True})
    for code, name in PERMISSIONS:
        Permission.objects.update_or_create(codigo=code, defaults={
            'modulo': 'products', 'grupo': 'Taxonomias', 'nome': name,
            'descricao': name, 'criticidade': 30, 'protegida': False,
            'ativo': True, 'removido_em': None,
        })


class Migration(migrations.Migration):
    dependencies = [('products', '0007_tipoprodutosegmento_and_more')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
