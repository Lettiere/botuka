from django.core.management.base import BaseCommand

from apps.core.search.service import GlobalSearchService


class Command(BaseCommand):
    help = 'Audita models, querysets públicos e correspondências da busca global sem alterar dados.'

    def add_arguments(self, parser):
        parser.add_argument('--query', default='botucatu', help='Termo usado na consulta de amostra.')

    def handle(self, *args, **options):
        service = GlobalSearchService()
        query = options['query'].strip()[:120]
        failures = 0
        self.stdout.write(f'AUDITORIA DA BUSCA GLOBAL · consulta: {query!r}')
        for spec in service.registry:
            try:
                queryset = spec.queryset()
                manager = getattr(queryset.model, 'all_objects', queryset.model._default_manager)
                total = manager.count()
                public = queryset.count()
                matches = len(GlobalSearchService((spec,)).search(query)[0])
                self.stdout.write(
                    f'{spec.label.upper()}\n'
                    f'  model: {queryset.model._meta.label}\n'
                    f'  total banco: {total}\n'
                    f'  públicos: {public}\n'
                    f'  registrados na busca: sim\n'
                    f'  resultados para {query!r}: {matches}\n'
                    f'  campos: {", ".join(spec.fields)}'
                )
            except Exception as exc:
                failures += 1
                self.stderr.write(self.style.ERROR(
                    f'{spec.label.upper()}\n  ERRO: {type(exc).__name__}: {exc}'
                ))
        if failures:
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS('Auditoria concluída sem erros de queryset/campos.'))
