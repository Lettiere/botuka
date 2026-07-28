from django.db import migrations

PERMISSIONS = {
    "news.acessar_modulo": "Acessar módulo Notícias", "news.criar_artigo": "Criar artigo",
    "news.editar_artigo_proprio": "Editar artigo próprio", "news.editar_artigo_terceiro": "Editar artigo de terceiro",
    "news.visualizar_artigo_proprio": "Visualizar artigo próprio", "news.visualizar_artigo_terceiro": "Visualizar artigo de terceiro",
    "news.revisar_artigo": "Revisar artigo", "news.aprovar_artigo": "Aprovar artigo",
    "news.devolver_correcao": "Devolver para correção", "news.publicar_artigo": "Publicar artigo",
    "news.despublicar_artigo": "Despublicar artigo", "news.agendar_publicacao": "Agendar publicação",
    "news.destacar_artigo": "Destacar artigo", "news.arquivar_artigo": "Arquivar artigo",
    "news.restaurar_artigo": "Restaurar artigo", "news.atribuir_autor": "Atribuir autor",
    "news.gerenciar_configuracoes": "Gerenciar configurações editoriais",
}
PROFILES = {
    "NEWS_AUTOR": ["news.acessar_modulo", "news.criar_artigo", "news.editar_artigo_proprio", "news.visualizar_artigo_proprio"],
    "NEWS_EDITOR": ["news.acessar_modulo", "news.visualizar_artigo_terceiro", "news.revisar_artigo", "news.devolver_correcao", "news.aprovar_artigo"],
    "NEWS_PUBLICADOR": ["news.acessar_modulo", "news.visualizar_artigo_terceiro", "news.publicar_artigo", "news.despublicar_artigo", "news.agendar_publicacao", "news.destacar_artigo"],
    "NEWS_MODERADOR": ["news.acessar_modulo", "news.visualizar_artigo_terceiro", "news.revisar_artigo", "news.aprovar_artigo", "news.devolver_correcao", "news.arquivar_artigo"],
    "NEWS_ADMIN_MODULO": list(PERMISSIONS),
}

def seed(apps, schema_editor):
    Permission, Profile, Link = (apps.get_model("core", name) for name in ("Permissao", "Perfil", "PerfilPermissao"))
    permissions = {}
    for code, label in PERMISSIONS.items():
        permissions[code], _ = Permission.objects.update_or_create(codigo=code, defaults={"nome": label, "modulo": "news", "grupo": "Notícias", "ativo": True})
    for name, codes in PROFILES.items():
        profile, _ = Profile.objects.get_or_create(nome=name, defaults={"descricao": "Perfil funcional do módulo Notícias"})
        for code in codes:
            Link.objects.get_or_create(perfil=profile, permissao=permissions[code])

class Migration(migrations.Migration):
    dependencies = [("core", "0005_permissao_criticidade_permissao_grupo_and_more")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
