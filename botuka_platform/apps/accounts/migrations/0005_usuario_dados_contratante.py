from django.db import migrations, models
import apps.accounts.validators


class Migration(migrations.Migration):
    dependencies = [('accounts', '0004_seed_papeis_globais')]

    operations = [
        migrations.AddField(model_name='usuario', name='bairro', field=models.CharField(blank=True, max_length=120, verbose_name='bairro ou região')),
        migrations.AddField(model_name='usuario', name='cep', field=models.CharField(blank=True, max_length=8, verbose_name='CEP')),
        migrations.AddField(model_name='usuario', name='complemento', field=models.CharField(blank=True, max_length=120, verbose_name='complemento')),
        migrations.AddField(model_name='usuario', name='cpf_validado_em', field=models.DateTimeField(blank=True, null=True, verbose_name='CPF validado em')),
        migrations.AddField(model_name='usuario', name='endereco', field=models.CharField(blank=True, max_length=180, verbose_name='endereço')),
        migrations.AddField(model_name='usuario', name='numero', field=models.CharField(blank=True, max_length=20, verbose_name='número')),
        migrations.AddField(model_name='usuario', name='termos_contratante_aceitos_em', field=models.DateTimeField(blank=True, null=True, verbose_name='termos de contratante aceitos em')),
        migrations.AddField(
            model_name='usuario', name='visibilidade_localizacao',
            field=models.CharField(
                choices=[('PUBLICA', 'Cidade e estado'), ('APROXIMADA', 'Cidade, estado e região'), ('PRIVADA', 'Privada')],
                default='PUBLICA', max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name='usuario', name='cpf',
            field=models.CharField(
                blank=True, db_index=True, max_length=11,
                validators=[apps.accounts.validators.validar_cpf],
                verbose_name='CPF',
            ),
        ),
        migrations.AddConstraint(
            model_name='usuario',
            constraint=models.UniqueConstraint(
                condition=~models.Q(cpf=''), fields=('cpf',), name='platform_usuario_cpf_uk',
            ),
        ),
    ]
