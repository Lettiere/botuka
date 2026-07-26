from django.db import migrations
from django.utils.text import slugify


PERMISSOES = {
    'yubotuka.dashboard.visualizar': ('Visualizar dashboard do YuBotuka', 10),
    'yubotuka.video.criar': ('Criar vídeo no YuBotuka', 10),
    'yubotuka.video.editar_proprio': ('Editar vídeo próprio no YuBotuka', 10),
    'yubotuka.video.editar_todos': ('Editar todos os vídeos do YuBotuka', 40),
    'yubotuka.video.enviar_analise': ('Enviar vídeo para análise', 20),
    'yubotuka.video.aprovar': ('Aprovar vídeo do YuBotuka', 30),
    'yubotuka.video.rejeitar': ('Rejeitar vídeo do YuBotuka', 30),
    'yubotuka.video.publicar': ('Publicar vídeo do YuBotuka', 40),
    'yubotuka.video.agendar': ('Agendar vídeo do YuBotuka', 30),
    'yubotuka.video.arquivar': ('Arquivar vídeo do YuBotuka', 30),
    'yubotuka.video.destacar': ('Destacar vídeo do YuBotuka', 30),
    'yubotuka.canal.gerenciar': ('Gerenciar canais do YuBotuka', 40),
    'yubotuka.categoria.gerenciar': ('Gerenciar categorias do YuBotuka', 30),
    'yubotuka.playlist.gerenciar': ('Gerenciar playlists do YuBotuka', 30),
}


def migrar_episodios(apps, schema_editor):
    Episodio = apps.get_model('media', 'Episodio')
    Categoria = apps.get_model('media', 'CategoriaYuBotuka')
    Video = apps.get_model('media', 'Video')

    categorias = {}
    for episodio in Episodio.objects.select_related('programa', 'programa__canal').iterator():
        categoria = None
        nome_categoria = (episodio.programa.categoria or '').strip()
        if nome_categoria:
            chave = nome_categoria.casefold()
            categoria = categorias.get(chave)
            if categoria is None:
                categoria = Categoria.objects.filter(nome__iexact=nome_categoria).first()
                if categoria is None:
                    slug_base = slugify(nome_categoria)[:140] or 'categoria'
                    slug = slug_base
                    sufixo = 2
                    while Categoria.objects.filter(slug=slug).exists():
                        slug = f'{slug_base}-{sufixo}'
                        sufixo += 1
                    categoria = Categoria.objects.create(nome=nome_categoria, slug=slug)
                categorias[chave] = categoria

        status = {
            'PUBLICADO': 'PUBLICADO',
            'AGENDADO': 'AGENDADO',
            'CANCELADO': 'ARQUIVADO',
        }.get(episodio.status, 'RASCUNHO')
        autor_id = episodio.programa.produtor_id or episodio.programa.apresentador_id
        video, _ = Video.objects.get_or_create(
            slug=episodio.slug,
            defaults={
                'titulo': episodio.titulo,
                'descricao_curta': (episodio.descricao or '')[:300],
                'descricao': episodio.descricao or '',
                'youtube_url': episodio.youtube_url or '',
                'video_id': episodio.video_id or '',
                'thumbnail': episodio.thumbnail or '',
                'duracao': episodio.duracao,
                'categoria_id': categoria.pk if categoria else None,
                'canal_id': episodio.programa.canal_id,
                'programa_id': episodio.programa_id,
                'data_gravacao': episodio.data_gravacao,
                'data_agendamento': episodio.data_programada,
                'publicado_em': episodio.publicado_em,
                'destaque': episodio.destaque,
                'publicar_na_home': episodio.destaque,
                'status': status,
                'autor_id': autor_id,
                'ativo': episodio.ativo,
                'criado_em': episodio.criado_em,
                'atualizado_em': episodio.atualizado_em,
                'excluido_em': episodio.excluido_em,
            },
        )
        Episodio.objects.filter(pk=episodio.pk).update(video_editorial_id=video.pk)


def criar_permissoes(apps, schema_editor):
    Permissao = apps.get_model('core', 'Permissao')
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


def reverter_permissoes(apps, schema_editor):
    Permissao = apps.get_model('core', 'Permissao')
    Permissao.objects.filter(codigo__in=PERMISSOES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_permissao_criticidade_permissao_grupo_and_more'),
        ('media', '0003_motivorejeicao_categoriayubotuka_playlist_video_and_more'),
    ]

    operations = [
        migrations.RunPython(migrar_episodios, migrations.RunPython.noop),
        migrations.RunPython(criar_permissoes, reverter_permissoes),
    ]
