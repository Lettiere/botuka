from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('advertising', '0003_campanha_observacoes_criativo_video_and_more')]
    operations = [
        migrations.AddField(
            model_name='planopublicitario', name='duracao_segundos',
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.AlterField(
            model_name='planopublicitario', name='nivel',
            field=models.PositiveSmallIntegerField(choices=[
                (0, 'Impacto / Takeover'), (1, 'Destaque Premium'),
                (2, 'Destaque Plus'), (3, 'Destaque Segmentado'),
                (4, 'Standard'),
            ]),
        ),
    ]
