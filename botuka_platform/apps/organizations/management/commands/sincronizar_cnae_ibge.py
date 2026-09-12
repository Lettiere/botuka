from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.organizations.models import CNAE, EmpresaCNAE


IBGE_URL = "https://servicodados.ibge.gov.br/api/v2/cnae/subclasses"
FONTE = "IBGE"
VERSAO = "CNAE 2.3"


def somente_digitos(valor) -> str:
    codigo = re.sub(r"\D", "", str(valor or ""))
    if not codigo:
        return ""
    return codigo.zfill(7)


class Command(BaseCommand):
    help = "Sincroniza a tabela CNAE local com as subclasses oficiais do IBGE."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analisa a sincronização sem gravar alterações.",
        )
        parser.add_argument(
            "--arquivo",
            help="Usa um JSON local no lugar da API do IBGE.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        arquivo = options.get("arquivo")

        self.stdout.write("=" * 72)
        self.stdout.write("BOTUKA — SINCRONIZAÇÃO CNAE / IBGE")
        self.stdout.write("=" * 72)

        dados = self._carregar_dados(arquivo)

        if not isinstance(dados, list):
            raise CommandError("Resposta do IBGE não é uma lista.")

        if len(dados) < 1000:
            raise CommandError(
                f"Resposta contém somente {len(dados)} CNAEs. "
                "Sincronização cancelada por segurança."
            )

        registros_ibge = {}

        for item in dados:
            registro = self._normalizar_item(item)
            codigo = registro["codigo"]

            if not codigo:
                raise CommandError("Registro do IBGE sem código.")

            if codigo in registros_ibge:
                raise CommandError(
                    f"Código duplicado recebido do IBGE: {codigo}"
                )

            registros_ibge[codigo] = registro

        self.stdout.write(f"Registros recebidos do IBGE: {len(registros_ibge)}")

        existentes = list(CNAE.objects.all().order_by("id"))

        self.stdout.write(f"CNAEs atualmente no Botuka: {len(existentes)}")
        self.stdout.write(
            f"Vínculos Empresa/CNAE: {EmpresaCNAE.objects.count()}"
        )

        mapa_existentes = {}

        for cnae in existentes:
            codigo_normalizado = somente_digitos(cnae.codigo)

            if not codigo_normalizado:
                raise CommandError(
                    f"CNAE local ID {cnae.pk} possui código inválido: "
                    f"{cnae.codigo!r}"
                )

            anterior = mapa_existentes.get(codigo_normalizado)

            if anterior is not None and anterior.pk != cnae.pk:
                raise CommandError(
                    "COLISÃO LOCAL DE CNAE: "
                    f"{anterior.pk}/{anterior.codigo} e "
                    f"{cnae.pk}/{cnae.codigo} normalizam para "
                    f"{codigo_normalizado}. Nenhuma alteração foi feita."
                )

            mapa_existentes[codigo_normalizado] = cnae

        novos = []
        alterados = []
        inalterados = []

        campos = (
            "codigo",
            "descricao",
            "secao",
            "secao_descricao",
            "divisao",
            "divisao_descricao",
            "grupo",
            "grupo_descricao",
            "classe",
            "classe_descricao",
            "subclasse",
            "atividades",
            "classe_observacoes",
            "observacoes",
            "fonte",
            "versao",
            "ativo",
        )

        for codigo, registro in registros_ibge.items():
            atual = mapa_existentes.get(codigo)

            if atual is None:
                novos.append(registro)
                continue

            diferencas = {}

            for campo in campos:
                valor_atual = getattr(atual, campo)
                valor_novo = registro[campo]

                if valor_atual != valor_novo:
                    diferencas[campo] = (valor_atual, valor_novo)

            if diferencas:
                alterados.append((atual, registro, diferencas))
            else:
                inalterados.append(atual)

        codigos_ibge = set(registros_ibge)
        somente_local = [
            cnae
            for codigo, cnae in mapa_existentes.items()
            if codigo not in codigos_ibge
        ]

        self.stdout.write("")
        self.stdout.write("===== PLANO =====")
        self.stdout.write(f"Novos................: {len(novos)}")
        self.stdout.write(f"A atualizar...........: {len(alterados)}")
        self.stdout.write(f"Sem alteração.........: {len(inalterados)}")
        self.stdout.write(f"Somente na base local.: {len(somente_local)}")

        if somente_local:
            self.stdout.write("")
            self.stdout.write("===== CNAEs SOMENTE LOCAIS =====")
            for cnae in somente_local[:30]:
                self.stdout.write(
                    f"{cnae.pk} | {cnae.codigo} | {cnae.descricao[:100]}"
                )

            if len(somente_local) > 30:
                self.stdout.write(
                    f"... e mais {len(somente_local) - 30}"
                )

        self.stdout.write("")
        self.stdout.write("===== EXEMPLOS DE NOVOS =====")

        for registro in novos[:10]:
            self.stdout.write(
                f"{registro['codigo']} | {registro['descricao'][:110]}"
            )

        self.stdout.write("")
        self.stdout.write("===== EXEMPLOS DE ATUALIZAÇÕES =====")

        for atual, registro, diferencas in alterados[:10]:
            nomes = ", ".join(diferencas)
            self.stdout.write(
                f"ID {atual.pk} | {atual.codigo} | campos: {nomes}"
            )

        if dry_run:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN: nenhuma alteração foi gravada."
                )
            )
            return

        with transaction.atomic():
            criados = 0
            atualizados = 0

            for registro in novos:
                CNAE.objects.create(**registro)
                criados += 1

            for atual, registro, _ in alterados:
                for campo in campos:
                    setattr(atual, campo, registro[campo])

                atual.save(
                    update_fields=[
                        *campos,
                        "atualizado_em",
                    ]
                )
                atualizados += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronização concluída: "
                f"{criados} criados, {atualizados} atualizados."
            )
        )

        self.stdout.write(
            f"Total CNAEs no Botuka: {CNAE.objects.count()}"
        )
        self.stdout.write(
            f"Vínculos Empresa/CNAE preservados: "
            f"{EmpresaCNAE.objects.count()}"
        )

    def _carregar_dados(self, arquivo):
        if arquivo:
            self.stdout.write(f"Fonte: arquivo local {arquivo}")

            try:
                with open(arquivo, encoding="utf-8") as fp:
                    return json.load(fp)
            except (OSError, json.JSONDecodeError) as exc:
                raise CommandError(
                    f"Não foi possível ler {arquivo}: {exc}"
                ) from exc

        self.stdout.write(f"Fonte: {IBGE_URL}")

        requisicao = urllib.request.Request(
            IBGE_URL,
            headers={
                "User-Agent": "Botuka-CNAE-Sync/1.0",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                requisicao,
                timeout=60,
            ) as resposta:
                if resposta.status != 200:
                    raise CommandError(
                        f"IBGE respondeu HTTP {resposta.status}"
                    )

                conteudo = resposta.read().decode("utf-8")

        except urllib.error.URLError as exc:
            raise CommandError(
                f"Erro acessando API do IBGE: {exc}"
            ) from exc

        try:
            return json.loads(conteudo)
        except json.JSONDecodeError as exc:
            raise CommandError(
                f"Resposta inválida do IBGE: {exc}"
            ) from exc

    @staticmethod
    def _normalizar_item(item):
        classe = item.get("classe") or {}
        grupo = classe.get("grupo") or {}
        divisao = grupo.get("divisao") or {}
        secao = divisao.get("secao") or {}

        codigo = somente_digitos(item.get("id"))

        return {
            "codigo": codigo,
            "descricao": str(item.get("descricao") or "").strip(),
            "secao": str(secao.get("id") or "").strip(),
            "secao_descricao": str(
                secao.get("descricao") or ""
            ).strip(),
            "divisao": str(divisao.get("id") or "").strip(),
            "divisao_descricao": str(
                divisao.get("descricao") or ""
            ).strip(),
            "grupo": str(grupo.get("id") or "").strip(),
            "grupo_descricao": str(
                grupo.get("descricao") or ""
            ).strip(),
            "classe": str(classe.get("id") or "").strip(),
            "classe_descricao": str(
                classe.get("descricao") or ""
            ).strip(),
            "subclasse": codigo,
            "atividades": item.get("atividades") or [],
            "classe_observacoes": classe.get("observacoes") or [],
            "observacoes": item.get("observacoes") or [],
            "fonte": FONTE,
            "versao": VERSAO,
            "ativo": True,
        }
