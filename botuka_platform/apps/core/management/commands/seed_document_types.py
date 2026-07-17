from django.core.management.base import BaseCommand

from apps.core.models import DocumentoRequisito, TipoDocumento


TIPOS = [
    ('CPF', 'CPF', True, False, False),
    ('CIN', 'Carteira de Identidade Nacional', True, False, False),
    ('RG_LEGADO', 'RG legado', True, False, False),
    ('CNH', 'CNH', True, False, True),
    ('COMPROVANTE_ENDERECO', 'Comprovante de endereço', True, True, True),
    ('CONTRATO_SOCIAL', 'Contrato social', False, True, False),
    ('CARTAO_CNPJ', 'Cartão CNPJ', False, True, False),
    ('INSCRICAO_ESTADUAL', 'Inscrição estadual', False, True, False),
    ('OUTRO', 'Outro documento', True, True, False),
]

REQUISITOS = [
    ('CPF', 'PROPRIETARIO_EMPRESA', 'organizations', True),
    ('CPF', 'PRESTACAO_SERVICO', 'services', True),
    ('CNH', 'MOTORISTA', 'mobility', True),
    ('CARTAO_CNPJ', 'PROPRIETARIO_EMPRESA', 'organizations', True),
]


class Command(BaseCommand):
    help = 'Cadastra tipos e requisitos de documentos.'

    def handle(self, *args, **options):
        for codigo, nome, pf, pj, validade in TIPOS:
            TipoDocumento.objects.update_or_create(
                codigo=codigo,
                defaults={
                    'nome': nome,
                    'pessoa_fisica': pf,
                    'pessoa_juridica': pj,
                    'possui_validade': validade,
                    'ativo': True,
                },
            )

        for codigo, contexto, modulo, obrigatorio in REQUISITOS:
            tipo = TipoDocumento.objects.get(codigo=codigo)
            DocumentoRequisito.objects.update_or_create(
                tipo_documento=tipo,
                contexto=contexto,
                modulo=modulo,
                defaults={'obrigatorio': obrigatorio, 'ativo': True},
            )

        self.stdout.write(self.style.SUCCESS('Tipos e requisitos de documentos sincronizados.'))
