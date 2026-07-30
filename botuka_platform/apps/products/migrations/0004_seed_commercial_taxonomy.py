from django.db import migrations
from django.utils.text import slugify


SECTORS = {
    'Comércio': ['Produtos diversos'],
    'Automotivo': ['Automóveis', 'Motocicletas'],
    'Tecnologia': ['Celulares', 'Computadores'],
    'Casa e decoração': ['Móveis', 'Eletrodomésticos'],
    'Moda': ['Roupas', 'Calçados'],
    'Beleza': ['Beleza e cuidados'],
    'Alimentos': ['Alimentos embalados'],
    'Cultura e religião': ['Artigos religiosos', 'Instrumentos musicais'],
    'Agro': ['Produtos agrícolas'],
    'Indústria': ['Equipamentos industriais'],
    'Artesanato': ['Produtos artesanais'],
}

SEGMENTS = [
    'Católico', 'Evangélico', 'Espírita', 'Umbanda', 'Candomblé',
    'Quimbanda', 'Budista', 'Judaico', 'Islâmico', 'Hindu',
    'Tradições orientais', 'Espiritualidade', 'Outros',
]

ATTRIBUTES = {
    'Automóveis': [
        ('Marca', 'marca', 'TEXTO'), ('Modelo', 'modelo', 'TEXTO'),
        ('Ano', 'ano', 'INTEIRO'), ('Quilometragem', 'quilometragem', 'INTEIRO'),
        ('Combustível', 'combustivel', 'ESCOLHA'), ('Câmbio', 'cambio', 'ESCOLHA'),
        ('Cor', 'cor', 'TEXTO'), ('Número de portas', 'portas', 'INTEIRO'),
    ],
    'Celulares': [
        ('Marca', 'marca', 'TEXTO'), ('Modelo', 'modelo', 'TEXTO'),
        ('Armazenamento', 'armazenamento', 'TEXTO'), ('Memória', 'memoria', 'TEXTO'),
        ('Sistema operacional', 'sistema-operacional', 'ESCOLHA'), ('Cor', 'cor', 'TEXTO'),
    ],
    'Móveis': [
        ('Material', 'material', 'TEXTO'), ('Largura', 'largura', 'DECIMAL'),
        ('Altura', 'altura', 'DECIMAL'), ('Profundidade', 'profundidade', 'DECIMAL'),
        ('Cor', 'cor', 'TEXTO'), ('Montagem necessária', 'montagem-necessaria', 'BOOLEANO'),
    ],
}

OPTIONS = {
    'combustivel': ['Gasolina', 'Etanol', 'Flex', 'Diesel', 'Elétrico', 'Híbrido'],
    'cambio': ['Manual', 'Automático', 'Automatizado', 'CVT'],
    'sistema-operacional': ['Android', 'iOS', 'Outro'],
}


def seed(apps, schema_editor):
    Sector = apps.get_model('products', 'SetorProduto')
    Category = apps.get_model('products', 'CategoriaProduto')
    Segment = apps.get_model('products', 'SegmentoProduto')
    Attribute = apps.get_model('products', 'AtributoProduto')
    for order, (sector_name, categories) in enumerate(SECTORS.items(), start=1):
        sector, _ = Sector.objects.get_or_create(
            slug=slugify(sector_name), defaults={'nome': sector_name, 'ordem': order},
        )
        for category_name in categories:
            category, _ = Category.objects.get_or_create(
                setor=sector, slug=slugify(category_name),
                defaults={
                    'nome': category_name,
                    'exige_segmento': category_name == 'Artigos religiosos',
                },
            )
            for position, (name, key, kind) in enumerate(ATTRIBUTES.get(category_name, []), start=1):
                Attribute.objects.get_or_create(
                    categoria_taxonomia=category, chave=key,
                    defaults={
                        'nome': name, 'tipo': kind, 'ordem': position,
                        'opcoes': OPTIONS.get(key, []),
                    },
                )
    for name in SEGMENTS:
        Segment.objects.get_or_create(slug=slugify(name), defaults={'nome': name})


class Migration(migrations.Migration):
    dependencies = [('products', '0003_categoriaproduto_segmentoproduto_setorproduto_and_more')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
