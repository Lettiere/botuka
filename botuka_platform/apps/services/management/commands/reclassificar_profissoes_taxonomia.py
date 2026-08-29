from pathlib import Path
from django.core.management.base import BaseCommand
from apps.services.taxonomy_commercial import apply_safe_classification, load_safe_classification_plan

class Command(BaseCommand):
    help = 'Valida e, somente com --apply, reclassifica as profissões do lote seguro.'
    def add_arguments(self, parser):
        default = Path(__file__).resolve().parents[5] / '_auditoria_cbo'
        parser.add_argument('--directory', type=Path, default=default)
        parser.add_argument('--apply', action='store_true')
    def handle(self, *args, **options):
        if options['apply']:
            result = apply_safe_classification(options['directory'])
            self.stdout.write(self.style.SUCCESS(f'RECLASSIFICAÇÃO APLICADA: {result}'))
        else:
            plan = load_safe_classification_plan(options['directory'])
            changed = sum((x['profissao'].setor_id, x['profissao'].area_id) != (x['setor'].id, x['area'].id) for x in plan)
            self.stdout.write(self.style.SUCCESS(f'DRY-RUN VALIDADO; banco não alterado: processed={len(plan)}, would_change={changed}'))
