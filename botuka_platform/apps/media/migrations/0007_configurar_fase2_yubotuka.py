from django.db import migrations


PERMISSOES = {
    'yubotuka.tag.gerenciar': ('Gerenciar tags do YuBotuka', 30),
    'yubotuka.apresentador.gerenciar': ('Gerenciar apresentadores do YuBotuka', 30),
    'yubotuka.convidado.gerenciar': ('Gerenciar convidados do YuBotuka', 30),
    'yubotuka.patrocinador.gerenciar': ('Gerenciar patrocinadores do YuBotuka', 30),
    'yubotuka.banner.gerenciar': ('Gerenciar banners do YuBotuka', 40),
    'yubotuka.motivo_rejeicao.gerenciar': ('Gerenciar motivos de rejeição do YuBotuka', 30),
    'yubotuka.config.gerenciar': ('Gerenciar configurações do YuBotuka', 40),
    'yubotuka.auditoria.visualizar': ('Visualizar auditoria do YuBotuka', 30),
}


def configurar_dados(apps, schema_editor):
    Configuracao = apps.get_model('media', 'ConfiguracaoYuBotuka')
    Destaque = apps.get_model('media', 'DestaqueEditorial')
    Episodio = apps.get_model('media', 'Episodio')
    Permissao = apps.get_model('core', 'Permissao')

    Configuracao.objects.get_or_create(
        pk=1,
        defaults={
            'titulo_publico': 'YuBotuka',
            'descricao_publica': 'Vídeos, programas e transmissões de Botucatu.',
        },
    )
    for episodio in Episodio.objects.select_related('video_editorial').filter(
        video_editorial__isnull=False,
    ):
        video = episodio.video_editorial
        tipo = episodio.tipo if episodio.tipo in {
            'VIDEO', 'SHORT', 'PODCAST', 'ENTREVISTA', 'ESPECIAL',
        } else 'LIVE' if episodio.tipo == 'TRANSMISSAO' else 'VIDEO'
        type(video).objects.filter(pk=video.pk).update(
            tipo=tipo,
            temporada_id=episodio.temporada_id,
            numero_episodio=episodio.numero,
        )
        if video.destaque:
            Destaque.objects.get_or_create(
                video_id=video.pk, posicao='YUBOTUKA',
                defaults={'ordem': 0, 'ativo': True},
            )
        if video.publicar_na_home:
            Destaque.objects.get_or_create(
                video_id=video.pk, posicao='HOME',
                defaults={'ordem': 0, 'ativo': True},
            )

    for codigo, (nome, criticidade) in PERMISSOES.items():
        Permissao.objects.update_or_create(
            codigo=codigo,
            defaults={
                'modulo': 'yubotuka',
                'grupo': 'YuBotuka',
                'nome': nome,
                'descricao': nome,
                'criticidade': criticidade,
                'protegida': criticidade >= 40,
                'ativo': True,
                'removido_em': None,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_permissao_criticidade_permissao_grupo_and_more'),
        ('media', '0006_apresentador_banneryubotuka_convidado_patrocinador_and_more'),
    ]

    operations = [
        migrations.RunPython(configurar_dados, migrations.RunPython.noop),
    ]
