import re
import unicodedata

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


CATALOGOS = ('Setor', 'AreaProfissional', 'Profissao', 'TipoServico')


def _normalizar(nome):
    nome = re.sub(r'\s+', ' ', (nome or '').strip()).casefold()
    return ''.join(
        caractere
        for caractere in unicodedata.normalize('NFKD', nome)
        if not unicodedata.combining(caractere)
    )


def preencher_metadados(apps, schema_editor):
    using = schema_editor.connection.alias
    for nome_modelo in CATALOGOS:
        modelo = apps.get_model('services', nome_modelo)
        for item in modelo.objects.using(using).only('pk', 'nome').iterator():
            modelo.objects.using(using).filter(pk=item.pk).update(
                origem='SISTEMA',
                status_catalogo='APROVADO',
                criado_por=None,
                nome_normalizado=_normalizar(item.nome),
            )

    vinculo = apps.get_model('services', 'ProfissaoTipoServico')
    vinculo.objects.using(using).update(
        origem='SISTEMA', status_catalogo='APROVADO', criado_por=None,
    )


def campos_moderacao(nome_modelo):
    nome = nome_modelo.lower()
    return [
        migrations.AddField(
            model_name=nome,
            name='origem',
            field=models.CharField(
                choices=[('SISTEMA', 'Sistema'), ('USUARIO', 'Usuário')],
                default='SISTEMA', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name=nome,
            name='status_catalogo',
            field=models.CharField(
                choices=[
                    ('APROVADO', 'Aprovado'), ('PENDENTE', 'Pendente'),
                    ('REJEITADO', 'Rejeitado'), ('MESCLADO', 'Mesclado'),
                ],
                default='APROVADO', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name=nome,
            name='criado_por',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]


operations = []
for catalogo in CATALOGOS:
    operations.extend(campos_moderacao(catalogo))
    nome = catalogo.lower()
    operations.extend([
        migrations.AddField(
            model_name=nome,
            name='nome_normalizado',
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
        migrations.AddField(
            model_name=nome,
            name='mesclado_com',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='itens_mesclados', to=f'services.{nome}',
            ),
        ),
    ])

operations.extend(campos_moderacao('ProfissaoTipoServico'))
operations.append(migrations.RunPython(preencher_metadados, migrations.RunPython.noop))


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0011_taxonomia_fiscal_tributaria'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = operations
