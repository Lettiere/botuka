from django.db import migrations


TABLES = (
    'products_setorproduto',
    'products_categoriaproduto',
    'products_familiaproduto',
    'products_tipoproduto',
    'products_segmentoproduto',
    'products_tipoprodutosegmento',
    'products_atributoproduto',
)


def move_tables(schema_editor, source, target, prepare_target=False):
    if schema_editor.connection.vendor != 'postgresql':
        raise RuntimeError(
            'A migration de schemas da taxonomia requer PostgreSQL.',
        )
    quote = schema_editor.connection.ops.quote_name
    with schema_editor.connection.cursor() as cursor:
        if prepare_target:
            cursor.execute(
                f'CREATE SCHEMA IF NOT EXISTS {quote(target)} AUTHORIZATION CURRENT_USER'
            )
            cursor.execute(
                f'GRANT USAGE, CREATE ON SCHEMA {quote(target)} TO CURRENT_USER'
            )
        for table in TABLES:
            cursor.execute(
                f'ALTER TABLE {quote(source)}.{quote(table)} '
                f'SET SCHEMA {quote(target)}'
            )


def forwards(apps, schema_editor):
    move_tables(schema_editor, 'public', 'taxonomy', prepare_target=True)


def backwards(apps, schema_editor):
    move_tables(schema_editor, 'taxonomy', 'public')
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP SCHEMA IF EXISTS "taxonomy"')


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ('products', '0010_align_product_editorial_columns'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards, backwards),
            ],
            state_operations=[
                migrations.AlterModelTable(
                    name='setorproduto',
                    table='"taxonomy"."products_setorproduto"',
                ),
                migrations.AlterModelTable(
                    name='categoriaproduto',
                    table='"taxonomy"."products_categoriaproduto"',
                ),
                migrations.AlterModelTable(
                    name='familiaproduto',
                    table='"taxonomy"."products_familiaproduto"',
                ),
                migrations.AlterModelTable(
                    name='tipoproduto',
                    table='"taxonomy"."products_tipoproduto"',
                ),
                migrations.AlterModelTable(
                    name='segmentoproduto',
                    table='"taxonomy"."products_segmentoproduto"',
                ),
                migrations.AlterModelTable(
                    name='tipoprodutosegmento',
                    table='"taxonomy"."products_tipoprodutosegmento"',
                ),
                migrations.AlterModelTable(
                    name='atributoproduto',
                    table='"taxonomy"."products_atributoproduto"',
                ),
            ],
        ),
    ]
