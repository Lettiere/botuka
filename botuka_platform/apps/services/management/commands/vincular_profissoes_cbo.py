from pathlib import Path

from django.core.management.base import BaseCommand

from apps.services.taxonomy_rollout import (
    apply_profession_cbo_plan,
    load_rollout_lots,
    validate_profession_cbo_plan,
)


class Command(BaseCommand):
    help = 'Valida e, somente com --apply, cria vínculos CBO do lote seguro.'

    def add_arguments(self, parser):
        default = Path(__file__).resolve().parents[5] / '_auditoria_cbo'
        parser.add_argument('--directory', type=Path, default=default)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        lots = load_rollout_lots(options['directory'])
        if options['apply']:
            result = apply_profession_cbo_plan(lots)
            self.stdout.write(self.style.SUCCESS(f'VÍNCULOS APLICADOS: {result}'))
            return
        plan = validate_profession_cbo_plan(lots)
        without_cbo = len(lots.safe) - len(plan)
        self.stdout.write(self.style.SUCCESS(
            f'DRY-RUN VALIDADO; banco não alterado: com_cbo={len(plan)}, sem_cbo={without_cbo}, editorial={len(lots.editorial)}'
        ))
