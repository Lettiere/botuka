from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.media.models import Canal, CategoriaYuBotuka, Playlist


THEMES = (
    ('Esportes', 'esportes', 'YuBotuka — Esportes'),
    ('Turismo', 'turismo', 'YuBotuka — Turismo'),
    ('Música', 'musica', 'YuBotuka — Música'),
    ('Cultura', 'cultura', 'YuBotuka — Cultura'),
    ('Religiosidade', 'religiosidade', 'YuBotuka — Religiosidade'),
)
RELIGIOUS = (
    ('YuBotuka — Catolicismo', 'catolicismo'),
    ('YuBotuka — Igrejas Evangélicas', 'evangelicos'),
    ('YuBotuka — Espiritismo', 'espiritismo'),
    ('YuBotuka — Religiões de Matriz Africana', 'matriz-africana'),
)


class Command(BaseCommand):
    help = 'Cria categorias e playlists temáticas de forma idempotente, sem criar vídeos.'

    def add_arguments(self, parser):
        parser.add_argument('--owner', required=True, help='Username do proprietário editorial.')
        parser.add_argument('--channel', default='', help='Slug; usa o canal oficial quando omitido.')

    @transaction.atomic
    def handle(self, *args, **options):
        owner = get_user_model().objects.filter(username=options['owner'], is_active=True).first()
        if not owner:
            raise CommandError('Usuário ativo não encontrado.')
        channels = Canal.objects.filter(ativo=True, excluido_em__isnull=True)
        channel = (
            channels.filter(slug=options['channel']).first()
            if options['channel'] else channels.filter(oficial=True).first()
        )
        if not channel:
            raise CommandError('Canal ativo não encontrado. Informe --channel.')
        created_categories = created_playlists = 0
        playlists = {}
        for order, (name, slug, playlist_name) in enumerate(THEMES, 1):
            category, made = CategoriaYuBotuka.objects.get_or_create(
                slug=slug, defaults={'nome': name, 'ordem': order, 'ativo': True},
            )
            created_categories += int(made)
            playlist, made = Playlist.objects.get_or_create(
                slug=slug,
                defaults={
                    'nome': playlist_name, 'canal': channel, 'categoria': category,
                    'proprietario': owner, 'ordem': order, 'ativo': True,
                },
            )
            created_playlists += int(made)
            playlists[slug] = playlist
        religion = playlists['religiosidade']
        for order, (name, slug) in enumerate(RELIGIOUS, 1):
            _, made = Playlist.objects.get_or_create(
                slug=slug,
                defaults={
                    'nome': name, 'canal': channel, 'categoria': religion.categoria,
                    'playlist_pai': religion, 'proprietario': owner,
                    'ordem': order, 'ativo': True,
                },
            )
            created_playlists += int(made)
        self.stdout.write(self.style.SUCCESS(
            f'Estrutura pronta: {created_categories} categorias e {created_playlists} playlists criadas; nenhum vídeo criado.'
        ))
