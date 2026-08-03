from django.db import migrations


COLUMN_RENAMES = (
    ("autorizado_por_id", "aprovado_por_id"),
    ("autorizado_em", "aprovado_em"),
    ("motivo_devolucao", "motivo_rejeicao"),
)


def get_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor,
            table_name,
        )
    return {column.name for column in description}


def rename_columns_forward(apps, schema_editor):
    table_name = "products_produto"
    quote = schema_editor.quote_name
    columns = get_columns(schema_editor, table_name)

    for old_name, new_name in COLUMN_RENAMES:
        if old_name in columns and new_name not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} "
                f"RENAME COLUMN {quote(old_name)} TO {quote(new_name)}"
            )
            columns.remove(old_name)
            columns.add(new_name)


def rename_columns_backward(apps, schema_editor):
    table_name = "products_produto"
    quote = schema_editor.quote_name
    columns = get_columns(schema_editor, table_name)

    for old_name, new_name in reversed(COLUMN_RENAMES):
        if new_name in columns and old_name not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} "
                f"RENAME COLUMN {quote(new_name)} TO {quote(old_name)}"
            )
            columns.remove(new_name)
            columns.add(old_name)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0009_produto_products_internal_code_uk"),
    ]

    operations = [
        migrations.RunPython(
            rename_columns_forward,
            rename_columns_backward,
        ),
    ]
