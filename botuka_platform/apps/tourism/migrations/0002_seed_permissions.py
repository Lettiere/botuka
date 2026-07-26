from django.db import migrations


CODES = """
TURISMO_LOCAL_VISUALIZAR_PAINEL
TURISMO_LOCAL_CADASTRAR
TURISMO_LOCAL_EDITAR_PROPRIOS
TURISMO_LOCAL_EDITAR_TODOS
TURISMO_LOCAL_EXCLUIR_PROPRIOS
TURISMO_LOCAL_EXCLUIR_TODOS
TURISMO_LOCAL_ENVIAR_ANALISE
TURISMO_LOCAL_PUBLICAR
TURISMO_LOCAL_PAUSAR
TURISMO_LOCAL_MODERAR
TURISMO_LOCAL_DESTACAR_HOME
TURISMO_FOTO_CADASTRAR
TURISMO_FOTO_EDITAR_PROPRIAS
TURISMO_FOTO_EXCLUIR_PROPRIAS
TURISMO_FOTO_MODERAR
TURISMO_VIDEO_CADASTRAR
TURISMO_VIDEO_EDITAR_PROPRIOS
TURISMO_VIDEO_EXCLUIR_PROPRIOS
TURISMO_VIDEO_MODERAR
TURISMO_PLAYLIST_CADASTRAR
TURISMO_PLAYLIST_EDITAR_PROPRIAS
TURISMO_PLAYLIST_MODERAR
TURISMO_GUIA_VISUALIZAR_PAINEL
TURISMO_GUIA_CADASTRAR
TURISMO_GUIA_EDITAR_PROPRIO
TURISMO_GUIA_EDITAR_TODOS
TURISMO_GUIA_VALIDAR
TURISMO_GUIA_PUBLICAR
TURISMO_GUIA_PAUSAR
TURISMO_GUIA_MODERAR
TURISMO_ROTEIRO_CADASTRAR
TURISMO_ROTEIRO_EDITAR_PROPRIOS
TURISMO_ROTEIRO_PUBLICAR
TURISMO_EXPERIENCIA_CADASTRAR
TURISMO_EXPERIENCIA_EDITAR_PROPRIAS
TURISMO_EXPERIENCIA_PUBLICAR
""".split()


def seed(apps, schema_editor):
    Permissao = apps.get_model('core', 'Permissao')
    for code in CODES:
        parts = code.split('_')
        group = parts[1].title()
        action = ' '.join(parts[2:]).lower()
        moderation = any(word in code for word in ('MODERAR', 'PUBLICAR', 'VALIDAR', 'TODOS', 'DESTACAR'))
        Permissao.objects.update_or_create(
            codigo=code,
            defaults={
                'modulo': 'Turismo', 'grupo': group,
                'nome': f'{group}: {action}',
                'descricao': f'Autoriza a ação {action} no módulo Turismo.',
                'criticidade': 30 if moderation else 20,
                'protegida': False, 'ativo': True,
            },
        )
    Permissao.objects.update_or_create(
        codigo='usuarios.permissoes.gerenciar',
        defaults={
            'modulo': 'Usuários', 'grupo': 'Permissões',
            'nome': 'Administrar permissões individuais',
            'descricao': 'Concede e revoga permissões individuais auditáveis.',
            'criticidade': 50, 'protegida': True, 'ativo': True,
        },
    )


def unseed(apps, schema_editor):
    apps.get_model('core', 'Permissao').objects.filter(codigo__in=CODES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tourism', '0001_initial'),
        ('core', '0005_permissao_criticidade_permissao_grupo_and_more'),
    ]
    operations = [migrations.RunPython(seed, unseed)]
