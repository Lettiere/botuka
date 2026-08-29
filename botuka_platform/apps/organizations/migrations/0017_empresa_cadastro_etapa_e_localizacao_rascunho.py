from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('organizations', '0016_empresa_atuacao')]
    operations = [
        migrations.AddField(
            model_name='empresa', name='cadastro_etapa',
            field=models.PositiveSmallIntegerField(
                db_column='platform_empresa_cadastro_etapa', default=1,
                verbose_name='etapa do cadastro',
            ),
        ),
        migrations.AlterField(
            model_name='empresa', name='cidade',
            field=models.ForeignKey(
                blank=True, null=True, db_column='platform_empresa_cidade_fk',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='empresas', to='locations.cidade',
                verbose_name='cidade',
            ),
        ),
        migrations.AlterField(
            model_name='empresa', name='estado',
            field=models.ForeignKey(
                blank=True, null=True, db_column='platform_empresa_estado_fk',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='empresas', to='locations.estado',
                verbose_name='estado',
            ),
        ),
    ]
