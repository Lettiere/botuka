from django.core.management.base import BaseCommand
from django.db import transaction

from apps.services.models import Setor


NOMES = {
    "Construção civil": "Construção Civil",
    "Tecnologia": "Tecnologia",
    "Saúde e bem-estar": "Saúde e Bem-Estar",
    "Beleza": "Beleza e Estética",
    "Educação": "Educação",
    "Transporte": "Transporte e Logística",
    "Eventos": "Eventos",
    "Serviços domésticos": "Serviços Domésticos",
    "Manutenção": "Manutenção e Reparos",
    "Automotivo": "Serviços Automotivos",
    "Jurídico": "Serviços Jurídicos",
    "Contabilidade": "Contabilidade e Finanças",
    "Marketing": "Marketing e Comunicação",
    "Alimentação": "Alimentação e Gastronomia",
    "Segurança": "Segurança e Proteção",
    "Limpeza": "Limpeza e Conservação",
    "Fotografia e audiovisual": "Fotografia e Audiovisual",
    "Agricultura e área rural": "Agricultura e Serviços Rurais",
}


class Command(BaseCommand):
    help = "Normaliza as nomenclaturas públicas dos setores do Botuka."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica efetivamente as alterações.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        aplicar = options["apply"]

        alterados = 0
        nao_encontrados = []

        for atual, novo in NOMES.items():
            setor = Setor.objects.filter(nome=atual).first()

            if not setor:
                # Permite reexecução segura caso já esteja normalizado.
                if Setor.objects.filter(nome=novo).exists():
                    self.stdout.write(
                        self.style.SUCCESS(f"OK JÁ NORMALIZADO: {novo}")
                    )
                    continue

                nao_encontrados.append(atual)
                continue

            if atual == novo:
                self.stdout.write(f"SEM ALTERAÇÃO: {atual}")
                continue

            self.stdout.write(f"{atual}  ->  {novo}")

            if aplicar:
                setor.nome = novo
                setor.save(update_fields=["nome"])

            alterados += 1

        self.stdout.write("")
        self.stdout.write(f"ALTERAÇÕES PREVISTAS={alterados}")
        self.stdout.write(f"NÃO ENCONTRADOS={len(nao_encontrados)}")

        for nome in nao_encontrados:
            self.stdout.write(self.style.WARNING(f"NÃO ENCONTRADO: {nome}"))

        if aplicar:
            self.stdout.write(self.style.SUCCESS("MANUTENÇÃO APLICADA"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN: nenhuma alteração foi gravada. "
                    "Use --apply somente após a auditoria."
                )
            )
