from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def vincular_concessoes(apps, schema_editor):
    Acesso = apps.get_model("accounts", "AcessoModulo")
    Concessao = apps.get_model("accounts", "ConcessaoPermissao")
    for concessao in Concessao.objects.filter(revogada_em__isnull=True).select_related("permissao"):
        modulo = concessao.permissao.modulo or concessao.permissao.codigo.split(".", 1)[0]
        acesso, _ = Acesso.objects.get_or_create(
            usuario_id=concessao.usuario_id, modulo=modulo, status="ATIVO",
            defaults={
                "escopo": concessao.escopo, "concedido_por_id": concessao.concedida_por_id,
                "valida_ate": concessao.valida_ate, "justificativa": concessao.justificativa,
                "observacao": concessao.observacao,
            },
        )
        concessao.acesso_id = acesso.pk
        concessao.save(update_fields=["acesso"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_concessaopermissao_escopo_perfil"),
        ("core", "0006_seed_module_access_profiles"),
    ]
    operations = [
        migrations.CreateModel(
            name="AcessoModulo",
            fields=[
                ("uuid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True, verbose_name="UUID")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="atualizado em")),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("modulo", models.CharField(db_index=True, max_length=60)),
                ("escopo", models.CharField(choices=[("PROPRIOS", "Próprios"), ("EQUIPE", "Equipe"), ("ORGANIZACAO", "Organização"), ("TODOS", "Todos")], default="PROPRIOS", max_length=16)),
                ("status", models.CharField(choices=[("ATIVO", "Ativo"), ("SUSPENSO", "Suspenso"), ("REVOGADO", "Revogado")], db_index=True, default="ATIVO", max_length=12)),
                ("valida_ate", models.DateTimeField(blank=True, null=True)),
                ("justificativa", models.TextField()),
                ("observacao", models.TextField(blank=True)),
                ("revogado_em", models.DateTimeField(blank=True, null=True)),
                ("concedido_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="acessos_modulos_concedidos", to=settings.AUTH_USER_MODEL)),
                ("perfil", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="acessos_modulos", to="core.perfil")),
                ("revogado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="acessos_modulos_revogados", to=settings.AUTH_USER_MODEL)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="acessos_modulos", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["usuario", "modulo"]},
        ),
        migrations.AddConstraint(
            model_name="acessomodulo",
            constraint=models.UniqueConstraint(condition=~models.Q(status="REVOGADO"), fields=("usuario", "modulo"), name="accounts_acesso_modulo_corrente_uk"),
        ),
        migrations.AddField(
            model_name="concessaopermissao", name="acesso",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="concessoes", to="accounts.acessomodulo"),
        ),
        migrations.RunPython(vincular_concessoes, migrations.RunPython.noop),
    ]
