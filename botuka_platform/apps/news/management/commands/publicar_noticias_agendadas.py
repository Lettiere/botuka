from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.db_routing import database_executor

from apps.news.services import publicar_agendados


class Command(BaseCommand):
    help = "Publica notícias agendadas cuja data e hora já foram alcançadas."

    def handle(self, *args, **options):
        with database_executor("worker"), transaction.atomic(using="worker"):
            quantidade = publicar_agendados()
        self.stdout.write(self.style.SUCCESS(f"{quantidade} notícia(s) publicada(s)."))
