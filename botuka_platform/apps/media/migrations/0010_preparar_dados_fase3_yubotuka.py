from django.db import migrations
from django.utils.text import slugify


PERMISSOES = {
    'yubotuka.programa.gerenciar': ('Gerenciar programas do YuBotuka', 30),
    'yubotuka.temporada.gerenciar': ('Gerenciar temporadas do YuBotuka', 30),
    'yubotuka.episodio.gerenciar': ('Gerenciar episódios do YuBotuka', 30),
    'yubotuka.transmissao.criar': ('Criar transmissão no YuBotuka', 20),
    'yubotuka.transmissao.editar_propria': ('Editar transmissão própria', 20),
    'yubotuka.transmissao.editar_todas': ('Editar todas as transmissões', 40),
    'yubotuka.transmissao.enviar_analise': ('Enviar transmissão para análise', 20),
    'yubotuka.transmissao.aprovar': ('Aprovar transmissão', 30),
    'yubotuka.transmissao.publicar': ('Publicar ou iniciar transmissão', 40),
    'yubotuka.transmissao.cancelar': ('Cancelar transmissão', 30),
    'yubotuka.canal.atribuir': ('Atribuir canais e usuários autorizados', 40),
    'yubotuka.legado.homologar': ('Homologar vídeos migrados', 40),
}


def preparar_dados(apps, schema_editor):
    Categoria = apps.get_model('media', 'CategoriaYuBotuka')
    Programa = apps.get_model('media', 'Programa')
    Transmissao = apps.get_model('media', 'Transmissao')
    Episodio = apps.get_model('media', 'Episodio')
    Homologacao = apps.get_model('media', 'HomologacaoVideoMigrado')
    Permissao = apps.get_model('core', 'Permissao')

    for programa in Programa.objects.exclude(categoria='').iterator():
        categoria = Categoria.objects.filter(nome__iexact=programa.categoria).first()
        if categoria:
            Programa.objects.filter(pk=programa.pk).update(categoria_editorial_id=categoria.pk)

    slugs = set(Transmissao.objects.exclude(slug__isnull=True).values_list('slug', flat=True))
    for transmissao in Transmissao.objects.select_related(
        'episodio', 'episodio__programa',
    ).iterator():
        episodio = transmissao.episodio
        titulo = transmissao.titulo or (episodio.titulo if episodio else f'Transmissão {transmissao.pk}')
        slug_base = slugify(titulo)[:220] or f'transmissao-{transmissao.pk}'
        slug = slug_base
        sufixo = 2
        while slug in slugs:
            slug = f'{slug_base[:215]}-{sufixo}'
            sufixo += 1
        slugs.add(slug)
        Transmissao.objects.filter(pk=transmissao.pk).update(
            titulo=titulo,
            slug=transmissao.slug or slug,
            descricao=transmissao.descricao or (episodio.descricao if episodio else ''),
            canal_id=transmissao.canal_id or (episodio.programa.canal_id if episodio else None),
            programa_id=transmissao.programa_id or (episodio.programa_id if episodio else None),
            video_id=transmissao.video_id or (episodio.video_id if episodio else ''),
            thumbnail=transmissao.thumbnail or (episodio.thumbnail if episodio else ''),
        )

    for episodio in Episodio.objects.select_related('video_editorial').filter(
        video_editorial__isnull=False,
    ):
        video = episodio.video_editorial
        divergencias = {}
        for campo_legado, campo_video in (
            ('titulo', 'titulo'), ('slug', 'slug'), ('youtube_url', 'youtube_url'),
            ('thumbnail', 'thumbnail'), ('status', 'status'),
        ):
            legado = getattr(episodio, campo_legado)
            novo = getattr(video, campo_video)
            if legado != novo:
                divergencias[campo_legado] = {'legado': legado, 'video': novo}
        if not episodio.youtube_url and video.youtube_url:
            divergencias['youtube_url']['aviso'] = (
                'O campo legado está vazio. Preservar a URL válida do Video.'
            )
        Homologacao.objects.get_or_create(
            video_id=video.pk,
            defaults={
                'episodio_legado_id': episodio.pk,
                'divergencias': divergencias,
            },
        )

    for codigo, (nome, criticidade) in PERMISSOES.items():
        Permissao.objects.update_or_create(
            codigo=codigo,
            defaults={
                'modulo': 'yubotuka', 'grupo': 'YuBotuka', 'nome': nome,
                'descricao': nome, 'criticidade': criticidade,
                'protegida': criticidade >= 40, 'ativo': True,
                'removido_em': None,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_permissao_criticidade_permissao_grupo_and_more'),
        ('media', '0009_programa_categoria_editorial_programa_ordem_and_more'),
    ]

    operations = [
        migrations.RunPython(preparar_dados, migrations.RunPython.noop),
    ]
