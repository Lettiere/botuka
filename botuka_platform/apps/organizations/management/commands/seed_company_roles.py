from django.core.management.base import BaseCommand

from apps.organizations.models import EmpresaFuncao


FUNCOES = [
    ('PROPRIETARIO', 'Proprietário'),
    ('ADMINISTRADOR', 'Administrador'),
    ('GERENTE', 'Gerente'),
    ('VENDEDOR', 'Vendedor'),
    ('PRESTADOR', 'Prestador'),
    ('ATENDENTE', 'Atendente'),
    ('MARKETING', 'Marketing'),
    ('FINANCEIRO', 'Financeiro'),
    ('COLABORADOR', 'Colaborador'),
    ('MOTORISTA', 'Motorista'),
]


class Command(BaseCommand):
    help = 'Cadastra funções empresariais.'

    def handle(self, *args, **options):
        for codigo, nome in FUNCOES:
            EmpresaFuncao.objects.update_or_create(
                codigo=codigo,
                defaults={'nome': nome, 'descricao': nome, 'ativo': True},
            )
        self.stdout.write(self.style.SUCCESS('Funções empresariais sincronizadas.'))
