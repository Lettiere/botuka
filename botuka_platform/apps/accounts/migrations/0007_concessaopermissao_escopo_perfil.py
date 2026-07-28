from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_auditoriapermissao_concessaopermissao")]
    operations = [
        migrations.AddField(
            model_name="concessaopermissao", name="escopo",
            field=models.CharField(
                choices=[
                    ("PROPRIOS", "Apenas registros próprios"),
                    ("EQUIPE", "Registros da própria equipe"),
                    ("ORGANIZACAO", "Registros da própria organização"),
                    ("TODOS", "Todos os registros do módulo"),
                ],
                db_index=True, default="PROPRIOS", max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="concessaopermissao", name="perfil_funcional",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
