from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0003_cidadebrasil_bairrocidade_estadobrasil_enderecocore_and_more')]

    operations = [
        migrations.AddField(
            model_name='auditoria', name='organizacao_uuid',
            field=models.UUIDField(blank=True, db_column='core_auditoria_organizacao_uuid', null=True),
        ),
        migrations.AddField(
            model_name='auditoria', name='sucesso',
            field=models.BooleanField(db_column='core_auditoria_sucesso', default=True),
        ),
        migrations.AddField(
            model_name='auditoria', name='origem',
            field=models.CharField(db_column='core_auditoria_origem', default='SISTEMA', max_length=40),
        ),
    ]
