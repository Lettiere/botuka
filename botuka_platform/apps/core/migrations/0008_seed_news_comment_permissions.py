from django.db import migrations


def seed(apps, schema_editor):
    Permission = apps.get_model("core", "Permissao")
    Profile = apps.get_model("core", "Perfil")
    Link = apps.get_model("core", "PerfilPermissao")
    permissions = {}
    for code, label in {
        "news.moderar_comentarios": "Moderar comentários de Notícias",
        "news.gerenciar_comentarios": "Gerenciar comentários de Notícias",
    }.items():
        permissions[code], _ = Permission.objects.update_or_create(
            codigo=code,
            defaults={
                "nome": label, "modulo": "news",
                "grupo": "Comentários", "ativo": True,
            },
        )
    for profile_name in ("NEWS_MODERADOR", "NEWS_ADMIN_MODULO"):
        profile = Profile.objects.filter(nome=profile_name).first()
        if profile:
            for permission in permissions.values():
                Link.objects.get_or_create(perfil=profile, permissao=permission)


class Migration(migrations.Migration):
    dependencies = [("core", "0007_seed_access_management_permissions")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
