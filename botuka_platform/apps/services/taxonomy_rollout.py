from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.services.models import CBOOcupacao, Profissao, ProfissaoCBO

SAFE_COUNT = 2669
EDITORIAL_COUNT = 546
TOTAL_COUNT = 3215


@dataclass(frozen=True)
class RolloutLots:
    safe: tuple[dict, ...]
    editorial: tuple[dict, ...]


def _read(path: Path) -> tuple[dict, ...]:
    if not path.is_file():
        raise ValidationError(f'Lote ausente: {path}')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = tuple(csv.DictReader(stream))
    required = {'profissao_id', 'profissao_uuid', 'status_homologacao'}
    if not rows or not required.issubset(rows[0]):
        raise ValidationError(f'Colunas obrigatórias ausentes em {path.name}')
    return rows


def load_rollout_lots(directory: str | Path) -> RolloutLots:
    directory = Path(directory)
    safe = _read(directory / 'lote_implementacao_segura.csv')
    editorial = _read(directory / 'lote_revisao_editorial.csv')
    if len(safe) != SAFE_COUNT or len(editorial) != EDITORIAL_COUNT:
        raise ValidationError(f'Contagens inesperadas: seguro={len(safe)}, editorial={len(editorial)}')
    safe_ids = [row['profissao_id'] for row in safe]
    editorial_ids = [row['profissao_id'] for row in editorial]
    all_ids = safe_ids + editorial_ids
    if len(all_ids) != TOTAL_COUNT or len(all_ids) != len(set(all_ids)):
        raise ValidationError('Lotes sobrepostos ou com profissão duplicada.')
    if any(row['status_homologacao'] != 'HOMOLOGADO' for row in safe):
        raise ValidationError('Lote seguro contém registro não homologado.')
    if any(row['status_homologacao'] != 'PENDENTE_EDITORIAL' for row in editorial):
        raise ValidationError('Lote editorial contém registro com status inesperado.')
    return RolloutLots(safe=safe, editorial=editorial)


def require_safe_profession(profissao_id: int | str, lots: RolloutLots) -> dict:
    key = str(profissao_id)
    safe = {row['profissao_id']: row for row in lots.safe}
    if key in safe:
        return safe[key]
    if key in {row['profissao_id'] for row in lots.editorial}:
        raise ValidationError(f'Profissão {key} pertence ao lote editorial e não pode ser aplicada automaticamente.')
    raise ValidationError(f'Profissão {key} não consta nos lotes homologados.')


def validate_profession_cbo_plan(lots: RolloutLots) -> tuple[dict, ...]:
    editorial_ids = {int(row['profissao_id']) for row in lots.editorial}
    if ProfissaoCBO.objects.filter(profissao_id__in=editorial_ids).exists():
        raise ValidationError('Existe vínculo CBO para profissão do lote editorial.')
    rows = tuple(row for row in lots.safe if row['cbo_codigo'].strip())
    profession_ids = {int(row['profissao_id']) for row in rows}
    professions = Profissao.objects.in_bulk(profession_ids)
    if set(professions) != profession_ids:
        missing = sorted(profession_ids - set(professions))
        raise ValidationError(f'Profissões inexistentes no lote seguro: {missing[:10]}')
    codes = {row['cbo_codigo'].strip() for row in rows}
    occupations = CBOOcupacao.objects.in_bulk(codes, field_name='codigo')
    if set(occupations) != codes:
        missing = sorted(codes - set(occupations))
        raise ValidationError(f'Códigos CBO inexistentes: {missing[:10]}')
    plan = []
    for row in rows:
        profession = professions[int(row['profissao_id'])]
        if str(profession.uuid) != row['profissao_uuid']:
            raise ValidationError(f'UUID divergente para profissão {profession.id}.')
        occupation = occupations[row['cbo_codigo'].strip()]
        conflicting = ProfissaoCBO.objects.filter(
            profissao=profession, principal=True,
        ).exclude(ocupacao=occupation)
        if conflicting.exists():
            raise ValidationError(f'Profissão {profession.id} já possui outro CBO principal.')
        plan.append({'profissao': profession, 'ocupacao': occupation, 'confianca': row['confianca']})
    return tuple(plan)


@transaction.atomic
def apply_profession_cbo_plan(lots: RolloutLots) -> dict[str, int]:
    plan = validate_profession_cbo_plan(lots)
    Profissao.objects.select_for_update().filter(id__in=[item['profissao'].id for item in plan]).count()
    created = updated = unchanged = 0
    for item in plan:
        defaults = {
            'principal': True,
            'confianca': item['confianca'],
            'origem': 'TAXONOMIA_ETAPA_8_10',
            'observacao': 'Vínculo homologado no lote de implementação segura.',
            'ativo': True,
        }
        link, was_created = ProfissaoCBO.objects.get_or_create(
            profissao=item['profissao'], ocupacao=item['ocupacao'], defaults=defaults,
        )
        if was_created:
            created += 1
            continue
        changed = any(getattr(link, field) != value for field, value in defaults.items())
        if changed:
            for field, value in defaults.items():
                setattr(link, field, value)
            link.save(update_fields=[*defaults, 'atualizado_em'])
            updated += 1
        else:
            unchanged += 1
    return {'planned': len(plan), 'created': created, 'updated': updated, 'unchanged': unchanged}
