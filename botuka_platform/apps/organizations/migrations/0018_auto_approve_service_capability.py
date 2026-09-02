from django.db import migrations
from django.utils import timezone


def aprovar_capacidade_de_servicos(apps, schema_editor):
    EmpresaCapacidade = apps.get_model('organizations', 'EmpresaCapacidade')
    agora = timezone.now()
    EmpresaCapacidade.objects.filter(
        empresa__ativo=True,
        empresa__atuacao__in=['SERVICOS', 'COMERCIO_E_SERVICOS'],
        capacidade__ativo=True,
        capacidade__codigo='PRESTAR_SERVICOS',
        ativo=True,
        status='PENDENTE',
    ).update(
        status='APROVADA',
        aprovado_por=None,
        aprovado_em=agora,
        motivo_rejeicao='',
        atualizado_em=agora,
    )


class Migration(migrations.Migration):
    dependencies = [('organizations', '0017_empresa_cadastro_etapa_e_localizacao_rascunho')]

    operations = [
        migrations.RunPython(
            aprovar_capacidade_de_servicos,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
