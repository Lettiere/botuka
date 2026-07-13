from django.core.management.base import BaseCommand

from apps.core.models import EstadoBrasil


ESTADOS = [
    ('11', 'Rondônia', 'RO', 'NORTE'), ('12', 'Acre', 'AC', 'NORTE'),
    ('13', 'Amazonas', 'AM', 'NORTE'), ('14', 'Roraima', 'RR', 'NORTE'),
    ('15', 'Pará', 'PA', 'NORTE'), ('16', 'Amapá', 'AP', 'NORTE'),
    ('17', 'Tocantins', 'TO', 'NORTE'), ('21', 'Maranhão', 'MA', 'NORDESTE'),
    ('22', 'Piauí', 'PI', 'NORDESTE'), ('23', 'Ceará', 'CE', 'NORDESTE'),
    ('24', 'Rio Grande do Norte', 'RN', 'NORDESTE'), ('25', 'Paraíba', 'PB', 'NORDESTE'),
    ('26', 'Pernambuco', 'PE', 'NORDESTE'), ('27', 'Alagoas', 'AL', 'NORDESTE'),
    ('28', 'Sergipe', 'SE', 'NORDESTE'), ('29', 'Bahia', 'BA', 'NORDESTE'),
    ('31', 'Minas Gerais', 'MG', 'SUDESTE'), ('32', 'Espírito Santo', 'ES', 'SUDESTE'),
    ('33', 'Rio de Janeiro', 'RJ', 'SUDESTE'), ('35', 'São Paulo', 'SP', 'SUDESTE'),
    ('41', 'Paraná', 'PR', 'SUL'), ('42', 'Santa Catarina', 'SC', 'SUL'),
    ('43', 'Rio Grande do Sul', 'RS', 'SUL'), ('50', 'Mato Grosso do Sul', 'MS', 'CENTRO_OESTE'),
    ('51', 'Mato Grosso', 'MT', 'CENTRO_OESTE'), ('52', 'Goiás', 'GO', 'CENTRO_OESTE'),
    ('53', 'Distrito Federal', 'DF', 'CENTRO_OESTE'),
]


class Command(BaseCommand):
    help = 'Cadastra estados brasileiros sem importar todas as cidades.'

    def handle(self, *args, **options):
        total = 0
        for codigo, nome, sigla, regiao in ESTADOS:
            EstadoBrasil.objects.update_or_create(
                sigla=sigla,
                defaults={
                    'codigo_ibge': codigo,
                    'nome': nome,
                    'regiao_brasileira': regiao,
                    'ativo': True,
                },
            )
            total += 1
        self.stdout.write(self.style.SUCCESS(f'{total} estados sincronizados.'))
