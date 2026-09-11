from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('organizations', '0019_empresa_criado_por_e_proprietario_opcional')]

    operations = [
        migrations.AddField(
            model_name='empresa', name='origem_cadastro',
            field=models.CharField(blank=True, null=True, max_length=12,
                choices=[('MANUAL', 'Manual'), ('API', 'API'), ('ADMIN', 'Administração'), ('MIGRACAO', 'Migração')],
                db_column='platform_empresa_origem_cadastro', verbose_name='origem do cadastro',
                help_text='Nulo identifica registros legados cuja origem não pode ser inferida com segurança.'),
        ),
        migrations.CreateModel(
            name='EmpresaImportacaoExecucao',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('fonte', models.CharField(default='MINHA_RECEITA', max_length=40)),
                ('tipo_execucao', models.CharField(choices=[('INICIAL', 'Inicial'), ('SEMANAL', 'Semanal'), ('MANUAL', 'Manual')], max_length=10)),
                ('status', models.CharField(choices=[('PENDENTE', 'Pendente'), ('EXECUTANDO', 'Executando'), ('CONCLUIDA', 'Concluída'), ('ERRO', 'Erro')], default='PENDENTE', max_length=12)),
                ('iniciada_em', models.DateTimeField(blank=True, null=True)), ('finalizada_em', models.DateTimeField(blank=True, null=True)),
                ('cursor_atual', models.TextField(blank=True)), ('paginas_processadas', models.PositiveIntegerField(default=0)),
                ('registros_recebidos', models.PositiveBigIntegerField(default=0)), ('registros_validos', models.PositiveBigIntegerField(default=0)),
                ('importados', models.PositiveBigIntegerField(default=0)), ('ja_existentes', models.PositiveBigIntegerField(default=0)),
                ('rejeitados', models.PositiveBigIntegerField(default=0)), ('erros', models.PositiveBigIntegerField(default=0)),
                ('ultima_mensagem', models.TextField(blank=True)), ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': '"platform"."platform_empresa_importacao_execucao_tb"', 'ordering': ('-criado_em',)},
        ),
        migrations.AddConstraint(model_name='empresaimportacaoexecucao', constraint=models.UniqueConstraint(
            fields=('fonte',), condition=models.Q(status='EXECUTANDO'), name='platform_empresa_import_running_uk')),
    ]
