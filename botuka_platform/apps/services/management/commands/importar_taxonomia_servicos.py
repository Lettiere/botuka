from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.services.models import AreaProfissional, Profissao, Setor


CATALOG_DIR = Path(settings.BASE_DIR).parent / 'scripts' / 'auditoria_taxonomia_servicos' / 'catalogo_completo'
EXPECTED_CONFIRMATION = 'APLICAR-SOMENTE-LOCAL'


def read_csv(name):
    with (CATALOG_DIR / name).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def validate_catalog():
    sectors = read_csv('01_SETORES.csv')
    areas = read_csv('02_AREAS_PROFISSIONAIS.csv')
    professions = read_csv('03_PROFISSOES.csv')
    digest = hashlib.sha256((CATALOG_DIR / '04_HIERARQUIA_COMPLETA.csv').read_bytes()).hexdigest()
    expected = (CATALOG_DIR / '10_HASH_CATALOGO.txt').read_text(encoding='ascii').split()[0]
    if digest != expected:
        raise CommandError('Hash do catálogo divergente.')
    if len(sectors) < 40 or len(areas) < 200 or len(professions) < 1500:
        raise CommandError('Catálogo abaixo das metas mínimas.')
    sector_slugs = [row['setor_slug'] for row in sectors]
    area_keys = [(row['setor_slug'], row['area_slug']) for row in areas]
    profession_names = [(row['setor_slug'], row['profissao_nome'].casefold()) for row in professions]
    profession_slugs = [(row['setor_slug'], row['profissao_slug']) for row in professions]
    for label, values in (
        ('setor', sector_slugs), ('área', area_keys),
        ('nome de profissão', profession_names), ('slug de profissão', profession_slugs),
    ):
        duplicates = [value for value, count in Counter(values).items() if count > 1]
        if duplicates:
            raise CommandError(f'Duplicidade de {label}: {duplicates[:5]}')
    sector_set, area_set = set(sector_slugs), set(area_keys)
    if any(row['setor_slug'] not in sector_set for row in areas):
        raise CommandError('Área referencia setor inexistente.')
    if any((row['setor_slug'], row['area_slug']) not in area_set for row in professions):
        raise CommandError('Profissão referencia área inexistente.')
    if set(row['setor_slug'] for row in areas) != sector_set:
        raise CommandError('Existe setor sem área.')
    if set((row['setor_slug'], row['area_slug']) for row in professions) != area_set:
        raise CommandError('Existe área sem profissão.')
    return sectors, areas, professions, digest


class Command(BaseCommand):
    help = 'Valida e importa a taxonomia profissional de Serviços com segurança.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--confirm', default='')
        parser.add_argument('--allow-database', default='')
        parser.add_argument('--inactivate-demo', action='store_true')

    def handle(self, *args, **options):
        sectors, areas, professions, digest = validate_catalog()
        database = str(settings.DATABASES['default']['NAME'])
        host = str(settings.DATABASES['default']['HOST']).strip().casefold()
        local_host = host in {'127.0.0.1', 'localhost', '::1'}
        applying = options['apply']
        if applying and (
            options['confirm'] != EXPECTED_CONFIRMATION
            or options['allow_database'] != database
            or not local_host
        ):
            raise CommandError(
                'Aplicação bloqueada: exija host loopback, confirmação e nome exato do banco local.'
            )

        report = Counter()
        sequence_state = {}
        if not applying:
            with connection.cursor() as cursor:
                for model in (Setor, AreaProfissional, Profissao):
                    sequence = connection.ops.quote_name(
                        f'{model._meta.db_table.split(chr(34))[-2]}_{model._meta.pk.column}_seq'
                    )
                    # A identidade real é obtida do catálogo; não se assume o nome.
                    cursor.execute('SELECT pg_get_serial_sequence(%s, %s)', (model._meta.db_table, model._meta.pk.column))
                    sequence_name = cursor.fetchone()[0]
                    cursor.execute(f'SELECT last_value, is_called FROM {sequence_name}')
                    sequence_state[sequence_name] = cursor.fetchone()
        with transaction.atomic():
            sector_objects = {}
            for row in sectors:
                obj, created = Setor.objects.update_or_create(
                    slug=row['setor_slug'],
                    defaults={'nome': row['setor_nome'], 'ordem': int(row['setor_ordem']), 'ativo': True},
                )
                sector_objects[row['setor_slug']] = obj
                report['setores_criados' if created else 'setores_atualizados'] += 1
            area_objects = {}
            for row in areas:
                sector = sector_objects[row['setor_slug']]
                obj, created = AreaProfissional.objects.update_or_create(
                    setor=sector, nome=row['area_nome'],
                    defaults={'slug': row['area_slug'], 'ordem': int(row['area_ordem']), 'ativo': True},
                )
                area_objects[(row['setor_slug'], row['area_slug'])] = obj
                report['areas_criadas' if created else 'areas_atualizadas'] += 1
            for row in professions:
                sector = sector_objects[row['setor_slug']]
                area = area_objects[(row['setor_slug'], row['area_slug'])]
                _, created = Profissao.objects.update_or_create(
                    setor=sector, nome=row['profissao_nome'],
                    defaults={'area': area, 'slug': row['profissao_slug'], 'ativo': True},
                )
                report['profissoes_criadas' if created else 'profissoes_atualizadas'] += 1
            if options['inactivate_demo']:
                demo_sector = Setor.objects.filter(slug='servicos-demo').first()
                demo_profession = Profissao.objects.filter(slug='profissional-demo').first()
                if demo_sector:
                    demo_sector.ativo = False
                    demo_sector.save(update_fields=['ativo', 'atualizado_em'])
                    report['setores_demo_inativados'] = 1
                if demo_profession:
                    demo_profession.ativo = False
                    demo_profession.save(update_fields=['ativo', 'atualizado_em'])
                    report['profissoes_demo_inativadas'] = 1
            if not applying:
                transaction.set_rollback(True)

        if not applying:
            with connection.cursor() as cursor:
                for sequence_name, (last_value, is_called) in sequence_state.items():
                    cursor.execute('SELECT setval(%s::regclass, %s, %s)', (sequence_name, last_value, is_called))

        mode = 'APLICADO' if applying else 'DRY-RUN (rollback automático)'
        self.stdout.write(self.style.SUCCESS(f'{mode}: {dict(report)}; sha256={digest}'))
