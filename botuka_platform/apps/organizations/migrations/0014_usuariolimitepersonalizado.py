import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0013_fundacao_identidade_organizacional'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UsuarioLimitePersonalizado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True, verbose_name='UUID')),
                ('ativo', models.BooleanField(db_column='platform_usuario_limite_ativo', default=True)),
                ('empresas_ilimitadas', models.BooleanField(db_column='platform_usuario_limite_empresas_ilimitadas', default=False)),
                ('servicos_ilimitados', models.BooleanField(db_column='platform_usuario_limite_servicos_ilimitados', default=False)),
                ('limite_empresas', models.PositiveIntegerField(blank=True, db_column='platform_usuario_limite_empresas', null=True)),
                ('limite_servicos', models.PositiveIntegerField(blank=True, db_column='platform_usuario_limite_servicos', null=True)),
                ('inicio', models.DateTimeField(db_column='platform_usuario_limite_inicio', default=django.utils.timezone.now)),
                ('fim', models.DateTimeField(blank=True, db_column='platform_usuario_limite_fim', null=True)),
                ('motivo', models.CharField(db_column='platform_usuario_limite_motivo', max_length=255)),
                ('observacoes', models.TextField(blank=True, db_column='platform_usuario_limite_observacoes')),
                ('criado_em', models.DateTimeField(auto_now_add=True, db_column='platform_usuario_limite_criado_em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, db_column='platform_usuario_limite_atualizado_em')),
                ('concedido_por', models.ForeignKey(db_column='platform_usuario_limite_concedido_por_fk', on_delete=django.db.models.deletion.PROTECT, related_name='limites_comerciais_concedidos', to=settings.AUTH_USER_MODEL)),
                ('usuario', models.OneToOneField(db_column='platform_usuario_limite_usuario_fk', on_delete=django.db.models.deletion.CASCADE, related_name='limite_comercial_personalizado', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'platform_usuario_limite_personalizado_tb',
                'ordering': ('-atualizado_em',),
                'indexes': [models.Index(fields=['ativo', 'inicio', 'fim'], name='plat_usu_lim_vigencia_idx')],
            },
        ),
    ]
