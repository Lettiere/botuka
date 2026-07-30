from django.db import migrations


PERMISSIONS = {
    'products.acessar': ('Acesso', 'Acessar Produtos', 10),
    'products.visualizar': ('Acesso', 'Visualizar produtos', 10),
    'products.criar_proprio': ('Conteúdo', 'Criar produto próprio', 20),
    'products.criar_empresa': ('Conteúdo', 'Criar produto de empresa', 20),
    'products.editar_proprios': ('Conteúdo', 'Editar produtos próprios', 20),
    'products.editar_empresa': ('Conteúdo', 'Editar produtos da empresa', 20),
    'products.enviar_analise': ('Fluxo', 'Enviar produto para análise', 20),
    'products.publicar': ('Fluxo', 'Publicar produtos', 40),
    'products.moderar': ('Moderação', 'Moderar produtos', 30),
    'products.aprovar': ('Moderação', 'Aprovar produtos', 30),
    'products.rejeitar': ('Moderação', 'Rejeitar produtos', 30),
    'products.pausar': ('Fluxo', 'Pausar produtos', 30),
    'products.arquivar': ('Fluxo', 'Arquivar produtos', 30),
    'products.restaurar': ('Fluxo', 'Restaurar produtos', 30),
    'products.excluir': ('Administração', 'Excluir produtos', 40),
    'products.gerenciar_imagens': ('Conteúdo', 'Gerenciar imagens de produtos', 20),
    'products.visualizar_metricas': ('Métricas', 'Visualizar métricas de produtos', 20),
    'products.conceder_limite': ('Administração', 'Conceder limite de produtos', 50),
    'products.administrar_usuarios': ('Administração', 'Administrar produtos de usuários', 50),
    'products.administrar_empresas': ('Administração', 'Administrar produtos de empresas', 50),
    'products.administrar_todos': ('Administração', 'Administrar todos os produtos', 50),
}


def seed(apps, schema_editor):
    Permission = apps.get_model('core', 'Permissao')
    for code, (group, name, level) in PERMISSIONS.items():
        Permission.objects.update_or_create(codigo=code, defaults={
            'modulo': 'products', 'grupo': group, 'nome': name,
            'descricao': name, 'criticidade': level, 'protegida': level >= 40,
            'ativo': True, 'removido_em': None,
        })


def unseed(apps, schema_editor):
    apps.get_model('core', 'Permissao').objects.filter(codigo__in=PERMISSIONS).update(ativo=False)


class Migration(migrations.Migration):
    dependencies = [('products', '0001_initial'), ('core', '0007_seed_access_management_permissions')]
    operations = [migrations.RunPython(seed, unseed)]
