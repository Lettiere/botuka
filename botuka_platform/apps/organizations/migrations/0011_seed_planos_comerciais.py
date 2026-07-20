from decimal import Decimal

from django.db import migrations


PLANOS = (
    ('GRATUITO', 'Gratuito', 3, 0),
    ('BRONZE', 'Bronze', 6, 10),
    ('PRATA', 'Prata', 12, 20),
    ('OURO', 'Ouro', 18, 30),
    ('PREMIUM', 'Premium', 30, 40),
    ('EMPRESARIAL', 'Empresarial', 50, 50),
    ('CORPORATIVO', 'Corporativo', 100, 60),
    ('PERSONALIZADO', 'Personalizado', None, 70),
)


def configurar_planos(apps, schema_editor):
    Plano = apps.get_model('organizations', 'Plano')
    for codigo, nome, limite, ordem in PLANOS:
        plano = Plano.objects.filter(nome__iexact=nome).first()
        if plano is None:
            plano = Plano(nome=nome)
        plano.codigo = codigo
        plano.nome = nome
        plano.limite_servicos = limite
        plano.limite_empresas = None
        plano.empresas_inclusas = 1
        plano.preco_empresa_adicional = Decimal('50.00')
        plano.ilimitado_servicos = False
        plano.ilimitado_empresas = False
        plano.ordem = ordem
        plano.ativo = True
        plano.save()


class Migration(migrations.Migration):
    dependencies = [('organizations', '0010_contratacaoempresaadicional_and_more')]
    operations = [migrations.RunPython(configurar_planos, migrations.RunPython.noop)]
