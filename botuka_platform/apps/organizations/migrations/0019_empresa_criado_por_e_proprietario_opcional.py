from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0018_auto_approve_service_capability'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='empresa',
            name='usuario_proprietario',
            field=models.ForeignKey(
                blank=True,
                db_column='platform_empresa_usuario_proprietario_fk',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='empresas_proprietario_platform',
                to=settings.AUTH_USER_MODEL,
                verbose_name='usuário proprietário',
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='criado_por',
            field=models.ForeignKey(
                blank=True,
                db_column='platform_empresa_criado_por_fk',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='empresas_criadas_administrativamente',
                to=settings.AUTH_USER_MODEL,
                verbose_name='criado por',
            ),
        ),
    ]
