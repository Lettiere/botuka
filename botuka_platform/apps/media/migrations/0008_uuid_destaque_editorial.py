import uuid

from django.db import migrations, models


def preencher_uuids(apps, schema_editor):
    Destaque = apps.get_model('media', 'DestaqueEditorial')
    for destaque in Destaque.objects.filter(uuid__isnull=True).iterator():
        Destaque.objects.filter(pk=destaque.pk).update(uuid=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [
        ('media', '0007_configurar_fase2_yubotuka'),
    ]

    operations = [
        migrations.AddField(
            model_name='destaqueeditorial',
            name='uuid',
            field=models.UUIDField(
                db_column='media_destaque_uuid',
                editable=False,
                null=True,
            ),
        ),
        migrations.RunPython(preencher_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='destaqueeditorial',
            name='uuid',
            field=models.UUIDField(
                db_column='media_destaque_uuid',
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
