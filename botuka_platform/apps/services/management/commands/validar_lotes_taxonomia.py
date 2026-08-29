from pathlib import Path

from django.core.management.base import BaseCommand

from apps.services.taxonomy_rollout import load_rollout_lots


class Command(BaseCommand):
    help = 'Valida separação, status e contagens dos lotes seguro e editorial sem gravar no banco.'

    def add_arguments(self, parser):
        default = Path(__file__).resolve().parents[5] / '_auditoria_cbo'
        parser.add_argument('--directory', type=Path, default=default)

    def handle(self, *args, **options):
        lots = load_rollout_lots(options['directory'])
        self.stdout.write(self.style.SUCCESS(f'Lotes válidos: seguro={len(lots.safe)}, editorial={len(lots.editorial)}; banco não alterado.'))
