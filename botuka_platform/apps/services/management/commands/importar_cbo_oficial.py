from pathlib import Path

from django.core.management.base import BaseCommand

from apps.services.cbo_catalog import import_catalog, load_catalog


class Command(BaseCommand):
    help = 'Valida o catálogo oficial CBO 2002 e, somente com --apply, importa-o de forma idempotente.'

    def add_arguments(self, parser):
        default = Path(__file__).resolve().parents[5] / '_auditoria_cbo'
        parser.add_argument('--directory', type=Path, default=default)
        parser.add_argument('--apply', action='store_true', help='Grava o catálogo no banco. Sem esta opção, executa apenas dry-run.')

    def handle(self, *args, **options):
        catalog = load_catalog(options['directory'])
        counts = catalog.counts
        if options['apply']:
            import_catalog(catalog)
            mode = 'IMPORTADO'
        else:
            mode = 'DRY-RUN VALIDADO; banco não alterado'
        self.stdout.write(self.style.SUCCESS(f'{mode}: {counts}'))
