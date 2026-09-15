import apps.advertising.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('advertising', '0004_planopublicitario_duracao_segundos_and_more')]
    operations = [
        migrations.AddField(model_name='planopublicitario', name='descricao', field=models.TextField(blank=True)),
        migrations.AddField(model_name='posicionamento', name='descricao', field=models.TextField(blank=True)),
        migrations.AddField(model_name='posicionamento', name='largura_mobile', field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='posicionamento', name='altura_mobile', field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='posicionamento', name='proporcao_recomendada', field=models.CharField(blank=True, max_length=24)),
        migrations.AddField(model_name='posicionamento', name='tamanho_maximo_bytes', field=models.PositiveIntegerField(default=5242880)),
        migrations.AddField(model_name='posicionamento', name='formatos_permitidos', field=models.JSONField(blank=True, default=apps.advertising.models.formatos_criativo_padrao, help_text='Extensões sem ponto, por exemplo: jpg, png, webp, mp4, webm.')),
        migrations.AddField(model_name='posicionamento', name='permite_imagem', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='posicionamento', name='permite_video', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='posicionamento', name='permite_texto', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='posicionamento', name='dimensoes_obrigatorias', field=models.BooleanField(default=False)),
    ]
