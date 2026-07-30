from django.db import migrations


PERMISSIONS = {
    'products.gerenciar_atributos': ('Conteúdo', 'Gerenciar atributos', 30),
    'products.gerenciar_estoque': ('Conteúdo', 'Gerenciar estoque informativo', 20),
    'products.acessar_conversas': ('Negociação', 'Acessar conversas', 20),
    'products.responder_conversas': ('Negociação', 'Responder conversas', 20),
    'products.visualizar_denuncias': ('Moderação', 'Visualizar denúncias', 30),
    'products.moderar_denuncias': ('Moderação', 'Moderar denúncias', 40),
    'products.gerenciar_loja': ('Loja', 'Gerenciar loja', 30),
    'products.oferecer_whatsapp': ('Negociação', 'Oferecer WhatsApp comercial', 30),
    'products.oferecer_pagamento_online': ('Recursos futuros', 'Oferecer pagamento online futuramente', 50),
}


def seed(apps, schema_editor):
    Permission = apps.get_model('core', 'Permissao')
    for code, (group, name, level) in PERMISSIONS.items():
        Permission.objects.update_or_create(
            codigo=code,
            defaults={
                'modulo': 'products', 'grupo': group, 'nome': name,
                'descricao': name, 'criticidade': level,
                'protegida': level >= 40, 'ativo': True, 'removido_em': None,
            },
        )


class Migration(migrations.Migration):
    dependencies = [('products', '0004_seed_commercial_taxonomy')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
