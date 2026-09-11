from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from apps.integrations.minha_receita.exceptions import MinhaReceitaError
from apps.organizations.services.botucatu_discovery import discover_batch


class Command(BaseCommand):
    help = 'Descobre e importa empresas públicas ativas de Botucatu em lotes (dry-run por padrão).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--cursor')
        modo = parser.add_mutually_exclusive_group()
        modo.add_argument('--dry-run', action='store_true', help='Não grava nenhuma informação (padrão).')
        modo.add_argument('--importar', action='store_true', help='Importa explicitamente as candidatas.')
        parser.add_argument(
            '--detalhado', action='store_true',
            help='Exibe os dados completos das candidatas em dry-run.',
        )
        parser.add_argument(
            '--enriquecer', action='store_true',
            help='Complementa candidatas via OpenCNPJ/BrasilAPI antes do dry-run ou importação.',
        )

    def handle(self, *args, **options):
        dry_run = not options['importar']
        if options['detalhado'] and not dry_run:
            raise CommandError('--detalhado só pode ser usado em dry-run.')
        try:
            resultado = discover_batch(
                limit=options['limit'], cursor=options['cursor'], dry_run=dry_run,
                enriquecer=options['enriquecer'],
            )
        except (MinhaReceitaError, ValidationError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write('MODO: DRY-RUN' if dry_run else 'MODO: IMPORTAÇÃO EXPLÍCITA')
        self.stdout.write('CNPJ | NOME | BAIRRO | CNAE PRINCIPAL | SITUAÇÃO | RESULTADO')
        for item in resultado.itens:
            self.stdout.write(
                f'{item.cnpj} | {item.nome} | {item.bairro} | {item.cnae_principal} | '
                f'{item.situacao} | {item.resultado}'
            )
            if options['detalhado'] and item.resultado == 'CANDIDATA':
                self._escrever_detalhes(item)
        self.stdout.write(
            f'Recebidas={resultado.recebidas} Ativas válidas={resultado.ativas_validas} '
            f'Rejeitadas={resultado.rejeitadas} Já existentes={resultado.ja_existentes} '
            f'Candidatas={resultado.candidatas} Importadas={resultado.importadas}'
        )
        self.stdout.write(f'Próximo cursor: {resultado.proximo_cursor or "-"}')

    def _escrever_detalhes(self, item):
        principal = self._cnae_formatado(
            item.cnae_principal, item.cnae_principal_descricao,
        )
        secundarios = ', '.join(
            self._cnae_formatado(codigo, descricao)
            for codigo, descricao in item.cnaes_secundarios
        ) or 'não informado'
        campos = (
            ('CNPJ', item.cnpj),
            ('Razão social', item.razao_social),
            ('Nome fantasia', item.nome_fantasia),
            ('Situação cadastral', item.situacao),
            ('Porte', item.porte),
            ('Natureza jurídica', item.natureza_juridica),
            ('Data de abertura', item.data_abertura),
            ('CEP', item.cep),
            ('Logradouro/endereço', item.endereco),
            ('Número', item.numero),
            ('Complemento', item.complemento),
            ('Bairro', item.bairro),
            ('Cidade', item.cidade),
            ('UF', item.uf),
            ('Telefone', item.telefone),
            ('E-mail', item.email),
            ('WhatsApp', ''),
            ('CNAE principal', principal),
            ('CNAEs secundários', secundarios),
            ('Fonte descoberta', item.fonte_descoberta),
            ('Fonte enriquecimento', item.fonte_enriquecimento),
            ('Completude para revisão', item.completude),
            ('Campos ausentes para revisão', ', '.join(item.campos_ausentes_revisao)),
            ('Resultado da classificação', item.resultado),
        )
        self.stdout.write('  DETALHES DA CANDIDATA')
        for rotulo, valor in campos:
            self.stdout.write(f'  {rotulo}: {valor or "não informado"}')
        if item.campos_enriquecidos:
            origens = ', '.join(
                f'{campo} ({fonte})' for campo, fonte in item.campos_enriquecidos.items()
            )
            self.stdout.write(f'  Complementados: {origens}')
        if item.erros_enriquecimento:
            self.stdout.write(
                f'  Enriquecimento indisponível/parcial: {"; ".join(item.erros_enriquecimento)}'
            )

    @staticmethod
    def _cnae_formatado(codigo, descricao):
        if codigo and descricao:
            return f'{codigo} - {descricao}'
        return codigo or descricao or 'não informado'
