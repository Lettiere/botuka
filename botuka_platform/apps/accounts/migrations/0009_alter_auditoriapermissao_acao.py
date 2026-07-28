from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_acessomodulo_concessaopermissao_acesso")]
    operations = [
        migrations.AlterField(
            model_name="auditoriapermissao", name="acao",
            field=models.CharField(
                choices=[("CONCEDER", "Conceder"), ("REVOGAR", "Revogar"), ("ALTERAR", "Alterar")],
                max_length=12,
            ),
        ),
    ]
