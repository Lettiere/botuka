from django.db import migrations


PERMISSIONS = {
    "gestao.acessar": ("Gestão", "Acesso", "Acessar gestão"),
    "gestao.gerenciar_usuarios": ("Gestão", "Administração", "Gerenciar usuários"),
    "gestao.gerenciar_permissoes": ("Gestão", "Administração", "Gerenciar acessos e permissões"),
    "news.acessar": ("Notícias", "Acesso", "Acessar"),
    "news.visualizar": ("Notícias", "Acesso", "Visualizar"),
    "news.cadastrar": ("Notícias", "Conteúdo", "Cadastrar"),
    "news.editar_proprios": ("Notícias", "Conteúdo", "Editar próprios"),
    "news.editar_todos": ("Notícias", "Conteúdo", "Editar todos"),
    "media.acessar": ("YoBotuka", "Acesso", "Acessar"),
    "media.visualizar": ("YoBotuka", "Acesso", "Visualizar"),
    "media.cadastrar": ("YoBotuka", "Conteúdo", "Cadastrar"),
    "media.editar_proprios": ("YoBotuka", "Conteúdo", "Editar próprios"),
    "media.editar_todos": ("YoBotuka", "Conteúdo", "Editar todos"),
    "media.publicar": ("YoBotuka", "Fluxo", "Publicar"),
    "events.acessar": ("Eventos", "Acesso", "Acessar"),
    "events.visualizar": ("Eventos", "Acesso", "Visualizar"),
    "events.cadastrar": ("Eventos", "Conteúdo", "Cadastrar"),
    "events.editar_proprios": ("Eventos", "Conteúdo", "Editar próprios"),
    "events.editar_todos": ("Eventos", "Conteúdo", "Editar todos"),
    "events.publicar": ("Eventos", "Fluxo", "Publicar"),
    "sports.acessar": ("Esportes", "Acesso", "Acessar"),
    "sports.visualizar": ("Esportes", "Acesso", "Visualizar"),
    "sports.cadastrar": ("Esportes", "Conteúdo", "Cadastrar"),
    "sports.editar_proprios": ("Esportes", "Conteúdo", "Editar próprios"),
    "sports.editar_todos": ("Esportes", "Conteúdo", "Editar todos"),
    "sports.publicar": ("Esportes", "Fluxo", "Publicar"),
}


def seed(apps, schema_editor):
    Permission = apps.get_model("core", "Permissao")
    for code, (module, group, label) in PERMISSIONS.items():
        Permission.objects.update_or_create(
            codigo=code,
            defaults={"modulo": code.split(".", 1)[0], "grupo": group, "nome": label, "descricao": f"{module}: {label}", "ativo": True},
        )


class Migration(migrations.Migration):
    dependencies = [("core", "0006_seed_module_access_profiles")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
