from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.services.models import AreaProfissional, Profissao, Servico, Setor
from apps.services.taxonomy_rollout import load_rollout_lots


AREA_RESOLUTIONS = {
    ('Esportes e Atividades Físicas', 'Dança'): (
        'Dança Esportiva', 'danca-esportiva',
        'Área comercial pública para dança esportiva e atividades rítmicas.',
    ),
    ('Engenharia e Serviços Técnicos', 'Segurança do Trabalho'): (
        'Engenharia de Segurança do Trabalho', 'engenharia-de-seguranca-do-trabalho',
        'Área técnica para engenharia aplicada à segurança do trabalho.',
    ),
    ('Pets e Serviços Veterinários', 'Cuidados Domiciliares'): (
        'Cuidados Domiciliares para Pets', 'cuidados-domiciliares-para-pets',
        'Área para cuidados veterinários e assistência de pets em domicílio.',
    ),
}


@dataclass(frozen=True)
class CommercialCatalog:
    sectors: tuple[dict, ...]
    areas: tuple[dict, ...]


def _read(path: Path) -> tuple[dict, ...]:
    if not path.is_file():
        raise ValidationError(f'Catálogo ausente: {path}')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return tuple(csv.DictReader(stream))


def load_commercial_catalog(directory: str | Path) -> CommercialCatalog:
    directory = Path(directory)
    sectors = _read(directory / 'catalogo_setores_final_v1.csv')
    source_areas = _read(directory / 'catalogo_areas_final_v1.csv')
    if len(sectors) != 33 or any(row['status'] != 'HOMOLOGADO' for row in sectors):
        raise ValidationError('Catálogo de setores diverge dos 33 homologados.')
    if len(source_areas) != 256:
        raise ValidationError('Catálogo de áreas diverge das 256 esperadas.')
    if sum(row['status'] == 'EXPANSAO_FUTURA' for row in source_areas) != 15:
        raise ValidationError('Catálogo não contém exatamente 15 áreas de expansão futura.')
    areas = []
    for source in source_areas:
        row = dict(source)
        row['source_area'] = source['area']
        resolution = AREA_RESOLUTIONS.get((source['setor'], source['area']))
        if resolution:
            row['area'], row['slug'], row['descricao'] = resolution
            row['observacao'] = f'{source["observacao"]} Conflito global de slug resolvido de forma homologada.'
        areas.append(row)
    sector_names = {row['nome'] for row in sectors}
    if len(sector_names) != 33 or len({row['slug'] for row in sectors}) != 33:
        raise ValidationError('Nome ou slug duplicado no catálogo de setores.')
    pairs = {(row['setor'], row['area']) for row in areas}
    if len(pairs) != 256 or len({row['slug'] for row in areas}) != 256:
        raise ValidationError('Nome composto ou slug duplicado no catálogo resolvido de áreas.')
    if any(row['setor'] not in sector_names for row in areas):
        raise ValidationError('Área aponta para setor ausente no catálogo final.')
    return CommercialCatalog(sectors=sectors, areas=tuple(areas))


def write_resolved_area_catalog(catalog: CommercialCatalog, output: Path) -> None:
    fields = ('setor', 'area', 'slug', 'descricao', 'status', 'observacao')
    with output.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in catalog.areas)


def validate_catalog_db_plan(catalog: CommercialCatalog) -> dict[str, int]:
    created_sectors = created_areas = updated_sectors = updated_areas = 0
    for row in catalog.sectors:
        by_slug = Setor.objects.filter(slug=row['slug']).exclude(nome=row['nome'])
        if by_slug.exists():
            raise ValidationError(f'Slug de setor já usado por outro registro: {row["slug"]}')
        instance = Setor.objects.filter(nome=row['nome']).first()
        if instance is None:
            created_sectors += 1
        elif any((instance.slug, instance.descricao, instance.ativo) != (row['slug'], row['descricao'], True) for _ in [0]):
            updated_sectors += 1
    for row in catalog.areas:
        sector = Setor.objects.filter(nome=row['setor']).first()
        candidates = AreaProfissional.objects.none()
        if sector:
            candidates = AreaProfissional.objects.filter(setor=sector, nome__in={row['area'], row['source_area']})
            if candidates.count() > 1:
                raise ValidationError(f'Área final e área de origem coexistem: {row["setor"]}/{row["area"]}')
            collision = AreaProfissional.objects.filter(setor=sector, slug=row['slug']).exclude(pk__in=candidates.values('pk'))
            if collision.exists():
                raise ValidationError(f'Slug de área em conflito no setor: {row["setor"]}/{row["slug"]}')
        instance = candidates.first()
        if instance is None:
            created_areas += 1
        elif (instance.nome, instance.slug, instance.descricao, instance.ativo) != (row['area'], row['slug'], row['descricao'], True):
            updated_areas += 1
    return {
        'sectors_created': created_sectors, 'sectors_updated': updated_sectors,
        'areas_created': created_areas, 'areas_updated': updated_areas,
    }


@transaction.atomic
def apply_commercial_catalog(catalog: CommercialCatalog) -> dict[str, int]:
    validate_catalog_db_plan(catalog)
    sector_map = {}
    created_sectors = updated_sectors = created_areas = updated_areas = 0
    for row in catalog.sectors:
        instance = Setor.objects.select_for_update().filter(nome=row['nome']).first()
        values = {'slug': row['slug'], 'descricao': row['descricao'], 'ativo': True}
        if instance is None:
            instance = Setor.objects.create(nome=row['nome'], **values)
            created_sectors += 1
        else:
            changed = [field for field, value in values.items() if getattr(instance, field) != value]
            if changed:
                for field in changed:
                    setattr(instance, field, values[field])
                instance.save(update_fields=[*changed, 'atualizado_em'])
                updated_sectors += 1
        sector_map[row['nome']] = instance
    for row in catalog.areas:
        sector = sector_map[row['setor']]
        instance = AreaProfissional.objects.select_for_update().filter(
            setor=sector, nome__in={row['area'], row['source_area']},
        ).first()
        values = {'nome': row['area'], 'slug': row['slug'], 'descricao': row['descricao'], 'ativo': True}
        if instance is None:
            AreaProfissional.objects.create(setor=sector, **values)
            created_areas += 1
        else:
            changed = [field for field, value in values.items() if getattr(instance, field) != value]
            if changed:
                for field in changed:
                    setattr(instance, field, values[field])
                instance.save(update_fields=[*changed, 'atualizado_em'])
                updated_areas += 1
    return {'sectors_created': created_sectors, 'sectors_updated': updated_sectors, 'areas_created': created_areas, 'areas_updated': updated_areas}


def load_safe_classification_plan(directory: str | Path) -> tuple[dict, ...]:
    directory = Path(directory)
    lots = load_rollout_lots(directory)
    mapping = {row['profissao_id']: row for row in _read(directory / 'mapa_profissoes_taxonomia_v4.csv')}
    plan = []
    professions = Profissao.objects.in_bulk(int(row['profissao_id']) for row in lots.safe)
    for safe in lots.safe:
        row = mapping.get(safe['profissao_id'])
        if row is None or row['status_homologacao'] != 'HOMOLOGADO':
            raise ValidationError(f'Mapa homologado ausente para profissão {safe["profissao_id"]}.')
        profession = professions.get(int(safe['profissao_id']))
        if profession is None or str(profession.uuid) != safe['profissao_uuid']:
            raise ValidationError(f'Profissão/UUID divergente: {safe["profissao_id"]}.')
        area_name = AREA_RESOLUTIONS.get((row['setor_final'], row['area_final']), (row['area_final'],))[0]
        sector = Setor.objects.filter(nome=row['setor_final']).first()
        area = AreaProfissional.objects.filter(setor=sector, nome=area_name).first() if sector else None
        if sector is None or area is None:
            raise ValidationError(f'Destino inexistente: {row["setor_final"]}/{area_name}.')
        plan.append({'profissao': profession, 'setor': sector, 'area': area})
    return tuple(plan)


@transaction.atomic
def apply_safe_classification(directory: str | Path) -> dict[str, int]:
    lots = load_rollout_lots(directory)
    editorial_before = {
        row[0]: row[1:] for row in Profissao.objects.filter(
            id__in=[int(r['profissao_id']) for r in lots.editorial]
        ).values_list('id', 'setor_id', 'area_id')
    }
    plan = load_safe_classification_plan(directory)
    Profissao.objects.select_for_update().filter(id__in=[item['profissao'].id for item in plan]).count()
    changed = 0
    for item in plan:
        profession = item['profissao']
        if (profession.setor_id, profession.area_id) != (item['setor'].id, item['area'].id):
            Profissao.objects.filter(pk=profession.pk).update(setor=item['setor'], area=item['area'])
            changed += 1
    editorial_after = {
        row[0]: row[1:] for row in Profissao.objects.filter(
            id__in=editorial_before
        ).values_list('id', 'setor_id', 'area_id')
    }
    if editorial_before != editorial_after:
        raise ValidationError('Uma profissão editorial foi alterada; transação cancelada.')
    return {'processed': len(plan), 'changed': changed, 'unchanged': len(plan) - changed}


def validate_service_sync(directory: str | Path) -> tuple[Servico, ...]:
    lots = load_rollout_lots(directory)
    safe_ids = [int(row['profissao_id']) for row in lots.safe]
    affected = []
    for service in Servico.all_objects.select_related('profissao').filter(profissao_id__in=safe_ids):
        if (service.setor_id, service.area_id) != (service.profissao.setor_id, service.profissao.area_id):
            affected.append(service)
    return tuple(affected)


@transaction.atomic
def apply_service_sync(directory: str | Path) -> dict[str, int]:
    affected = validate_service_sync(directory)
    Servico.all_objects.select_for_update().filter(id__in=[service.id for service in affected]).count()
    for service in affected:
        Servico.all_objects.filter(pk=service.pk).update(
            setor_id=service.profissao.setor_id, area_id=service.profissao.area_id,
        )
    return {'updated': len(affected)}
