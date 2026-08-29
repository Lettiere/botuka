from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.services.models import (
    CBOFamilia,
    CBOGrandeGrupo,
    CBOOcupacao,
    CBOSinonimo,
    CBOSubgrupo,
    CBOSubgrupoPrincipal,
)


FILES = {
    'grandes_grupos': ('cbo2002-grande-grupo.csv', 1, 2),
    'subgrupos_principais': ('cbo2002-subgrupo-principal.csv', 2, 2),
    'subgrupos': ('cbo2002-subgrupo.csv', 3, 3),
    'familias': ('cbo2002-familia.csv', 4, 4),
    'ocupacoes': ('cbo2002-ocupacao.csv', 6, 6),
    'sinonimos': ('cbo2002-sinonimo.csv', 6, 6),
}


@dataclass(frozen=True)
class Catalog:
    grandes_grupos: tuple[dict, ...]
    subgrupos_principais: tuple[dict, ...]
    subgrupos: tuple[dict, ...]
    familias: tuple[dict, ...]
    ocupacoes: tuple[dict, ...]
    sinonimos: tuple[dict, ...]

    @property
    def counts(self):
        return {name: len(getattr(self, name)) for name in FILES}


def _read(path: Path, minimum: int, maximum: int) -> tuple[dict, ...]:
    if not path.is_file():
        raise ValidationError(f'Arquivo CBO ausente: {path}')
    with path.open(encoding='cp1252', newline='') as stream:
        reader = csv.DictReader(stream, delimiter=';')
        if reader.fieldnames != ['CODIGO', 'TITULO']:
            raise ValidationError(f'Cabeçalho inválido em {path.name}: {reader.fieldnames}')
        rows = []
        for line, row in enumerate(reader, start=2):
            codigo = (row['CODIGO'] or '').strip()
            titulo = (row['TITULO'] or '').strip()
            if not codigo.isdigit() or not minimum <= len(codigo) <= maximum or not titulo:
                raise ValidationError(f'Registro inválido em {path.name}:{line}')
            rows.append({'codigo': codigo, 'titulo': titulo})
    return tuple(rows)


def load_catalog(directory: str | Path) -> Catalog:
    directory = Path(directory)
    data = {
        name: _read(directory / filename, minimum, maximum)
        for name, (filename, minimum, maximum) in FILES.items()
    }
    unique_sections = ('grandes_grupos', 'subgrupos_principais', 'subgrupos', 'familias', 'ocupacoes')
    for name in unique_sections:
        codes = [row['codigo'] for row in data[name]]
        if len(codes) != len(set(codes)):
            raise ValidationError(f'Códigos duplicados em {FILES[name][0]}')

    gg = {row['codigo'] for row in data['grandes_grupos']}
    sgp = {row['codigo'] for row in data['subgrupos_principais']}
    sg = {row['codigo'] for row in data['subgrupos']}
    fam = {row['codigo'] for row in data['familias']}
    ocu = {row['codigo'] for row in data['ocupacoes']}
    checks = (
        ('subgrupo principal', data['subgrupos_principais'], gg, 1),
        ('subgrupo', data['subgrupos'], sgp, 2),
        ('família', data['familias'], sg, 3),
        ('ocupação', data['ocupacoes'], fam, 4),
        ('sinônimo', data['sinonimos'], ocu, 6),
    )
    for label, rows, parents, prefix_length in checks:
        for row in rows:
            if row['codigo'][:prefix_length] not in parents:
                raise ValidationError(f'{label.capitalize()} órfão: {row["codigo"]}')
    return Catalog(**data)


@transaction.atomic
def import_catalog(catalog: Catalog) -> dict[str, int]:
    grandes = {}
    for row in catalog.grandes_grupos:
        grandes[row['codigo']], _ = CBOGrandeGrupo.objects.update_or_create(codigo=row['codigo'], defaults={'titulo': row['titulo'], 'ativo': True})
    principais = {}
    for row in catalog.subgrupos_principais:
        principais[row['codigo']], _ = CBOSubgrupoPrincipal.objects.update_or_create(codigo=row['codigo'], defaults={'titulo': row['titulo'], 'grande_grupo': grandes[row['codigo'][:1]], 'ativo': True})
    subgrupos = {}
    for row in catalog.subgrupos:
        subgrupos[row['codigo']], _ = CBOSubgrupo.objects.update_or_create(codigo=row['codigo'], defaults={'titulo': row['titulo'], 'subgrupo_principal': principais[row['codigo'][:2]], 'ativo': True})
    familias = {}
    for row in catalog.familias:
        familias[row['codigo']], _ = CBOFamilia.objects.update_or_create(codigo=row['codigo'], defaults={'titulo': row['titulo'], 'subgrupo': subgrupos[row['codigo'][:3]], 'ativo': True})
    ocupacoes = {}
    for row in catalog.ocupacoes:
        ocupacoes[row['codigo']], _ = CBOOcupacao.objects.update_or_create(codigo=row['codigo'], defaults={'titulo': row['titulo'], 'familia': familias[row['codigo'][:4]], 'ativo': True})
    for row in catalog.sinonimos:
        CBOSinonimo.objects.update_or_create(ocupacao=ocupacoes[row['codigo']], titulo=row['titulo'], defaults={'ativo': True})
    return catalog.counts
