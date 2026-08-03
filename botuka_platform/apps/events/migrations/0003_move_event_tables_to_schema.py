from django.db import migrations


TABLES = (
    'events_evento',
    'events_historicoevento',
    'events_interesseevento',
)


def move_tables(schema_editor, source, target, prepare_target=False):
    if schema_editor.connection.vendor != 'postgresql':
        raise RuntimeError(
            'A migration de schemas de eventos requer PostgreSQL.',
        )
    quote = schema_editor.connection.ops.quote_name
    with schema_editor.connection.cursor() as cursor:
        if prepare_target:
            cursor.execute(
                f'CREATE SCHEMA IF NOT EXISTS {quote(target)} '
                'AUTHORIZATION CURRENT_USER'
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
    move_tables(schema_editor, 'public', 'events', prepare_target=True)


def backwards(apps, schema_editor):
    move_tables(schema_editor, 'events', 'public')
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP SCHEMA IF EXISTS "events"')


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ('events', '0002_seed_event_permissions'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards, backwards),
            ],
            state_operations=[
                migrations.AlterModelTable(
                    name='evento',
                    table='"events"."events_evento"',
                ),
                migrations.AlterModelTable(
                    name='historicoevento',
                    table='"events"."events_historicoevento"',
                ),
                migrations.AlterModelTable(
                    name='interesseevento',
                    table='"events"."events_interesseevento"',
                ),
            ],
        ),
    ]
