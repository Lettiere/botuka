from django.db import migrations


def criar_propriedades_atuais(apps, schema_editor):
    Empresa = apps.get_model('organizations', 'Empresa')
    EmpresaPropriedade = apps.get_model('organizations', 'EmpresaPropriedade')

    for empresa in Empresa.objects.exclude(usuario_proprietario_id__isnull=True):
        existe = EmpresaPropriedade.objects.filter(
            empresa_id=empresa.pk,
            atual=True,
            fim_em__isnull=True,
        ).exists()
        if existe:
            continue

        EmpresaPropriedade.objects.create(
            empresa_id=empresa.pk,
            usuario_id=empresa.usuario_proprietario_id,
            atual=True,
            origem='MIGRACAO',
            observacao='Registro criado a partir de usuario_proprietario existente.',
        )


def remover_propriedades_migradas(apps, schema_editor):
    EmpresaPropriedade = apps.get_model('organizations', 'EmpresaPropriedade')
    EmpresaPropriedade.objects.filter(origem='MIGRACAO').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0006_cnae_empresafuncao_empresa_aceita_leads_and_more'),
    ]

    operations = [
        migrations.RunPython(criar_propriedades_atuais, remover_propriedades_migradas),
    ]
