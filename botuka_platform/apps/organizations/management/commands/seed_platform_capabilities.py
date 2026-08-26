from django.core.management.base import BaseCommand

from apps.organizations.models import Capacidade


CAPACIDADES = [
    ('VENDER_PRODUTOS', 'Vender produtos'),
    ('PRESTAR_SERVICOS', 'Prestar serviços'),
    ('ACEITAR_AGENDAMENTOS', 'Aceitar agendamentos'),
    ('CONTRATAR_SERVICOS', 'Contratar serviços'),
    ('PUBLICAR_VAGAS', 'Publicar vagas'),
    ('GERAR_LEADS', 'Gerar leads'),
    ('RECEBER_LEADS', 'Receber leads'),
    ('ATUAR_COMO_VENDEDOR', 'Atuar como vendedor'),
    ('OPERAR_MOBILIDADE', 'Operar mobilidade'),
    ('EMITIR_DOCUMENTO_FISCAL', 'Emitir documento fiscal'),
    ('GERENCIAR_EQUIPE', 'Gerenciar equipe'),
    ('PUBLICAR_EVENTOS', 'Publicar eventos'),
]


class Command(BaseCommand):
    help = 'Cadastra capacidades da plataforma.'

    def handle(self, *args, **options):
        for codigo, nome in CAPACIDADES:
            Capacidade.objects.update_or_create(
                codigo=codigo,
                defaults={'nome': nome, 'descricao': nome, 'exige_aprovacao': True, 'ativo': True},
            )
        self.stdout.write(self.style.SUCCESS('Capacidades sincronizadas.'))
