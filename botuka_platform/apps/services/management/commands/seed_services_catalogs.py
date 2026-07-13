from django.core.management.base import BaseCommand

from apps.services.models import FormaCobranca, Profissao, Setor, TipoServico


SETORES = [
    'Construção civil', 'Tecnologia', 'Saúde e bem-estar', 'Beleza', 'Educação',
    'Transporte', 'Eventos', 'Serviços domésticos', 'Manutenção', 'Automotivo',
    'Jurídico', 'Contabilidade', 'Marketing', 'Alimentação', 'Segurança',
    'Limpeza', 'Fotografia e audiovisual', 'Agricultura e área rural',
]

TIPOS = [
    'Presencial', 'Remoto', 'Domiciliar', 'Consultoria', 'Manutenção',
    'Instalação', 'Reforma', 'Produção sob encomenda', 'Transporte',
    'Locação', 'Aula ou treinamento', 'Emergencial',
]

FORMAS = [
    'Por hora', 'Por diária', 'Por serviço', 'Por projeto', 'Por metro quadrado',
    'Por unidade', 'Mensal', 'A combinar', 'Orçamento personalizado',
]

CONSTRUCAO = [
    'Pedreiro', 'Pintor', 'Eletricista', 'Encanador', 'Azulejista', 'Gesseiro',
    'Marceneiro', 'Serralheiro', 'Arquiteto', 'Engenheiro civil',
    'Mestre de obras', 'Ajudante geral',
]


class Command(BaseCommand):
    help = 'Cadastra catálogos iniciais de serviços.'

    def handle(self, *args, **options):
        for ordem, nome in enumerate(SETORES, start=1):
            Setor.objects.update_or_create(nome=nome, defaults={'ordem': ordem, 'ativo': True})

        for nome in TIPOS:
            TipoServico.objects.update_or_create(nome=nome, defaults={'ativo': True})

        for nome in FORMAS:
            FormaCobranca.objects.update_or_create(nome=nome, defaults={'ativo': True})

        setor = Setor.objects.get(nome='Construção civil')
        for nome in CONSTRUCAO:
            Profissao.objects.update_or_create(setor=setor, nome=nome, defaults={'ativo': True})

        self.stdout.write(self.style.SUCCESS('Catálogos de serviços sincronizados.'))
