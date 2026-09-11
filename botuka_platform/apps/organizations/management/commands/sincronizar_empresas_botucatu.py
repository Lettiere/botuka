from django.core.management.base import BaseCommand, CommandError

from apps.organizations.models import EmpresaImportacaoExecucao
from apps.organizations.services.empresa_importacao import (
    SincronizacaoEmAndamento,
    sincronizar_empresas,
)


class Command(BaseCommand):
    help = 'Executa a varredura completa semanal da Minha Receita para Botucatu.'

    def add_arguments(self, parser):
        parser.add_argument('--retomar', type=int, help='ID de execução pendente/com erro a retomar.')
        parser.add_argument('--tipo', choices=('INICIAL', 'SEMANAL', 'MANUAL'), default='SEMANAL')

    def handle(self, *args, **options):
        try:
            execucao = sincronizar_empresas(
                tipo_execucao=options['tipo'], retomar_id=options['retomar'],
            )
        except (SincronizacaoEmAndamento, ValueError, EmpresaImportacaoExecucao.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'Execução #{execucao.pk} concluída: {execucao.paginas_processadas} páginas, '
            f'{execucao.importados} importadas.'
        ))
