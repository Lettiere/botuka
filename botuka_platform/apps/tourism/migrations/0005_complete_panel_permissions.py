from django.db import migrations


CODES = """
TURISMO_EMPRESA_VISUALIZAR_PAINEL
TURISMO_EMPRESA_CADASTRAR
TURISMO_EMPRESA_EDITAR_PROPRIAS
TURISMO_EMPRESA_EDITAR_TODAS
TURISMO_EMPRESA_ENVIAR_ANALISE
TURISMO_EMPRESA_PUBLICAR
TURISMO_EMPRESA_PAUSAR
TURISMO_EMPRESA_MODERAR
TURISMO_GUIA_ENVIAR_ANALISE
TURISMO_VIDEO_ENVIAR_ANALISE
TURISMO_VIDEO_PUBLICAR
TURISMO_VIDEO_PAUSAR
TURISMO_PLAYLIST_ENVIAR_ANALISE
TURISMO_PLAYLIST_PUBLICAR
TURISMO_PLAYLIST_PAUSAR
TURISMO_ROTEIRO_ENVIAR_ANALISE
TURISMO_ROTEIRO_PAUSAR
TURISMO_ROTEIRO_MODERAR
TURISMO_EXPERIENCIA_ENVIAR_ANALISE
TURISMO_EXPERIENCIA_PAUSAR
TURISMO_EXPERIENCIA_MODERAR
""".split()


def seed(apps, schema_editor):
    Permissao = apps.get_model('core', 'Permissao')
    for code in CODES:
        parts = code.split('_')
        group = parts[1].title()
        action = ' '.join(parts[2:]).lower()
        moderation = any(word in code for word in ('MODERAR', 'PUBLICAR', 'TODAS'))
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


def unseed(apps, schema_editor):
    apps.get_model('core', 'Permissao').objects.filter(codigo__in=CODES).delete()


class Migration(migrations.Migration):
    dependencies = [('tourism', '0004_experienciaturistica_acessibilidade_and_more')]
    operations = [migrations.RunPython(seed, unseed)]
