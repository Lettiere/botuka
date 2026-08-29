from pathlib import Path
from django.core.management.base import BaseCommand
from apps.services.taxonomy_commercial import apply_commercial_catalog, load_commercial_catalog, validate_catalog_db_plan, write_resolved_area_catalog

class Command(BaseCommand):
    help = 'Prepara e aplica, somente com --apply, os catálogos comerciais homologados.'
    def add_arguments(self, parser):
        default = Path(__file__).resolve().parents[5] / '_auditoria_cbo'
        parser.add_argument('--directory', type=Path, default=default)
        parser.add_argument('--apply', action='store_true')
    def handle(self, *args, **options):
        catalog = load_commercial_catalog(options['directory'])
        write_resolved_area_catalog(catalog, options['directory'] / 'catalogo_areas_final_v2_resolvido.csv')
        result = apply_commercial_catalog(catalog) if options['apply'] else validate_catalog_db_plan(catalog)
        prefix = 'CATÁLOGO APLICADO' if options['apply'] else 'DRY-RUN VALIDADO; banco não alterado'
        self.stdout.write(self.style.SUCCESS(f'{prefix}: {result}'))
