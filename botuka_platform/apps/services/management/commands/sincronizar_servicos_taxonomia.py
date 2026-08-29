from pathlib import Path
from django.core.management.base import BaseCommand
from apps.services.taxonomy_commercial import apply_service_sync, validate_service_sync

class Command(BaseCommand):
    help = 'Valida e, somente com --apply, sincroniza setor/área de Serviços do lote seguro.'
    def add_arguments(self, parser):
        default = Path(__file__).resolve().parents[5] / '_auditoria_cbo'
        parser.add_argument('--directory', type=Path, default=default)
        parser.add_argument('--apply', action='store_true')
    def handle(self, *args, **options):
        if options['apply']:
            result = apply_service_sync(options['directory'])
            self.stdout.write(self.style.SUCCESS(f'SERVIÇOS SINCRONIZADOS: {result}'))
        else:
            affected = validate_service_sync(options['directory'])
            self.stdout.write(self.style.SUCCESS(f'DRY-RUN VALIDADO; banco não alterado: would_update={len(affected)}'))
