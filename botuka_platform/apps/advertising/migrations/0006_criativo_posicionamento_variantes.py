import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('advertising', '0005_commercial_configuration'),
    ]

    operations = [
        migrations.AddField(
            model_name='criativo',
            name='imagem_mobile',
            field=models.ImageField(blank=True, upload_to='advertising/criativos/mobile/'),
        ),
        migrations.AddField(
            model_name='criativo',
            name='posicionamento',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='criativos',
                to='advertising.posicionamento',
            ),
        ),
        migrations.AddField(
            model_name='criativo',
            name='video_mobile',
            field=models.FileField(blank=True, upload_to='advertising/criativos/videos/mobile/'),
        ),
        migrations.AddIndex(
            model_name='criativo',
            index=models.Index(
                fields=['campanha', 'posicionamento', 'ativo', 'aprovado'],
                name='adv_criativo_slot_idx',
            ),
        ),
    ]
