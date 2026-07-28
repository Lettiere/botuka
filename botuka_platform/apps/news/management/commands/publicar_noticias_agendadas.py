from django.core.management.base import BaseCommand

from apps.news.services import publicar_agendados


class Command(BaseCommand):
    help = "Publica notícias agendadas cuja data e hora já foram alcançadas."

    def handle(self, *args, **options):
        quantidade = publicar_agendados()
        self.stdout.write(self.style.SUCCESS(f"{quantidade} notícia(s) publicada(s)."))
