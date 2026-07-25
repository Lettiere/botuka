import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def preencher_criador_e_status(apps, schema_editor):
    Vaga = apps.get_model('recruitment', 'Vaga')
    Vaga.objects.filter(usuario_criador__isnull=True).update(
        usuario_criador=models.F('usuario_responsavel')
    )
    Vaga.objects.filter(status='PENDENTE').update(status='EM_ANALISE')


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('accounts', '0005_usuario_dados_contratante'),
        ('recruitment', '0003_curriculo_constraints'),
    ]

    operations = [
        migrations.AddField(model_name='vaga', name='aceita_candidatura_simplificada', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='vaga', name='area_atuacao', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name='vaga', name='categoria', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name='vaga', name='destaque', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='vaga', name='endereco_privado', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='vaga', name='ocultar_salario', field=models.BooleanField(default=False)),
        migrations.AddField(
            model_name='vaga', name='perfil_pessoa_fisica',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='vagas_como_pessoa_fisica', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='vaga', name='usuario_criador',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='vagas_criadas', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='vaga', name='visibilidade_localizacao',
            field=models.CharField(choices=[('PUBLICA', 'Cidade e estado'), ('APROXIMADA', 'Cidade, estado e bairro/região'), ('PRIVADA', 'Localização privada')], default='PUBLICA', max_length=12),
        ),
        migrations.AlterField(model_name='vaga', name='empresa', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='vagas', to='organizations.empresa')),
        migrations.AlterField(
            model_name='vaga', name='status',
            field=models.CharField(
                choices=[('RASCUNHO', 'Rascunho'), ('EM_ANALISE', 'Em análise'), ('PUBLICADA', 'Publicada'), ('PAUSADA', 'Pausada'), ('ENCERRADA', 'Encerrada'), ('EXPIRADA', 'Expirada'), ('REJEITADA', 'Rejeitada')],
                default='RASCUNHO', max_length=20,
            ),
        ),
        migrations.RunPython(preencher_criador_e_status, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='vaga', name='usuario_criador',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vagas_criadas', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='vaga',
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(empresa__isnull=False) & models.Q(perfil_pessoa_fisica__isnull=True))
                    | (models.Q(empresa__isnull=True) & models.Q(perfil_pessoa_fisica__isnull=False))
                ),
                name='recruit_vaga_responsavel_xor_ck',
            ),
        ),
        migrations.CreateModel(
            name='VagaAuditoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acao', models.CharField(max_length=40)),
                ('contexto', models.JSONField(blank=True, default=dict)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('vaga', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='auditoria', to='recruitment.vaga')),
            ],
            options={'db_table': 'recruitment_vaga_auditoria_tb', 'ordering': ['-criado_em']},
        ),
        migrations.CreateModel(
            name='CandidaturaHistorico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status_anterior', models.CharField(blank=True, max_length=20)),
                ('status_novo', models.CharField(max_length=20)),
                ('observacao', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('candidatura', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historico', to='recruitment.candidatura')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'recruitment_candidatura_historico_tb', 'ordering': ['-criado_em']},
        ),
    ]


