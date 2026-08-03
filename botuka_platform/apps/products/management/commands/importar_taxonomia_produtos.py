import csv
from collections import Counter
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from apps.products.models import (
    CategoriaProduto, FamiliaProduto, SegmentoProduto, SetorProduto,
    TipoProduto, TipoProdutoSegmento,
)


class ImportHasErrors(Exception):
    pass


class Command(BaseCommand):
    help = 'Importa a taxonomia completa de produtos de forma atômica e idempotente.'
    HEADERS = {
        'setores': {'nome', 'slug', 'descricao', 'ordem', 'ativo'},
        'categorias': {'setor_slug', 'nome', 'slug', 'descricao', 'ordem', 'ativo'},
        'familias': {'categoria_slug', 'nome', 'slug', 'descricao', 'ordem', 'ativo'},
        'tipos': {'categoria_slug', 'familia_slug', 'nome', 'slug', 'descricao', 'ordem', 'permite_segmento', 'exige_segmento', 'ativo'},
    }
    EXTRA_HEADERS = {
        'grupos_segmentos': {'nome', 'slug', 'ordem', 'ativo'},
        'segmentos': {'grupo_slug', 'nome', 'slug', 'ordem', 'ativo'},
        'tipos_grupos': {'categoria_slug', 'familia_slug', 'tipo_slug', 'grupo_slug', 'ativo'},
        'tipos_segmentos': {'categoria_slug', 'familia_slug', 'tipo_slug', 'grupo_slug', 'segmento_slug', 'ativo'},
        'atributos': {'categoria_slug', 'familia_slug', 'tipo_slug', 'codigo', 'nome', 'slug', 'tipo_dado', 'ativo'},
        'opcoes_atributos': {'atributo_codigo', 'valor', 'slug', 'ordem', 'ativo'},
    }

    def add_arguments(self, parser):
        for kind in self.HEADERS:
            parser.add_argument(f'--{kind}', type=Path)
        parser.add_argument('--grupos-segmentos', dest='grupos_segmentos', type=Path)
        parser.add_argument('--segmentos', type=Path)
        parser.add_argument('--tipos-grupos', dest='tipos_grupos', type=Path)
        parser.add_argument('--tipos-segmentos', dest='tipos_segmentos', type=Path)
        parser.add_argument('--atributos', type=Path)
        parser.add_argument('--opcoes-atributos', dest='opcoes_atributos', type=Path)
        parser.add_argument('--arquivo', type=Path, help='CSV consolidado com a coluna nivel.')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--aplicar', action='store_true', help='Confirma explicitamente a persistência.')

    def handle(self, *args, **options):
        paths = {kind: options.get(kind) for kind in self.HEADERS if options.get(kind)}
        extra_paths = {kind: options.get(kind) for kind in self.EXTRA_HEADERS if options.get(kind)}
        if options.get('arquivo'):
            paths.update(self._split_complete(options['arquivo']))
        if not paths and not extra_paths:
            raise CommandError('Informe ao menos um CSV ou --arquivo.')
        if options['dry_run'] == options['aplicar']:
            raise CommandError('Escolha exatamente uma opção: --dry-run ou --aplicar.')
        incompatible = {'grupos_segmentos', 'tipos_grupos', 'atributos', 'opcoes_atributos'} & extra_paths.keys()
        if options['aplicar'] and incompatible:
            raise CommandError(
                'Aplicação recusada: o schema atual não representa grupos de segmentos '
                'nem atributos por tipo. Use --dry-run até existir modelagem aprovada.'
            )
        report = {'criados': Counter(), 'ignorados': Counter(), 'duplicados': Counter(), 'erros': [], 'conflitos': []}
        rolled_back = False
        try:
            with transaction.atomic():
                for kind in self.HEADERS:
                    source = paths.get(kind)
                    if source:
                        getattr(self, f'_import_{kind}')(source, report)
                context = self._validate_extras(extra_paths, report)
                if extra_paths.get('segmentos'):
                    self._import_segmentos(extra_paths['segmentos'], report)
                if extra_paths.get('tipos_segmentos'):
                    self._import_tipos_segmentos(extra_paths['tipos_segmentos'], report)
                if report['erros']:
                    raise ImportHasErrors
                if options['dry_run']:
                    transaction.set_rollback(True)
                    rolled_back = True
        except ImportHasErrors:
            rolled_back = True
        self._report(report, options['dry_run'], rolled_back)
        if report['erros']:
            raise CommandError('A importação contém erros; nenhum registro foi persistido.')

    def _split_complete(self, path):
        rows = list(self._rows(path, {'nivel'}))
        grouped = {kind: [] for kind in self.HEADERS}
        aliases = {'setor': 'setores', 'categoria': 'categorias', 'familia': 'familias', 'tipo': 'tipos'}
        for line, row in rows:
            kind = aliases.get(row.get('nivel', '').casefold())
            if not kind:
                raise CommandError(f'{path.name}, linha {line}: nível inválido.')
            grouped[kind].append((line, row))
        return {kind: value for kind, value in grouped.items() if value}

    def _rows(self, source, required):
        if isinstance(source, list):
            yield from source
            return
        if not source.is_file():
            raise CommandError(f'Arquivo não encontrado: {source}')
        with source.open('r', encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise CommandError(f'{source}: colunas obrigatórias ausentes: {", ".join(sorted(missing))}.')
            for line, row in enumerate(reader, 2):
                clean = {key: (value or '').strip() for key, value in row.items()}
                if any(clean.values()):
                    yield line, clean

    @staticmethod
    def _bool(value, field):
        value = value.casefold()
        if value in {'1', 'true', 'sim', 'yes'}:
            return True
        if value in {'0', 'false', 'não', 'nao', 'no'}:
            return False
        raise ValidationError(f'{field}: use sim/não, true/false ou 1/0.')

    @staticmethod
    def _order(value):
        try:
            result = int(value or 0)
        except ValueError as exc:
            raise ValidationError('ordem deve ser um inteiro não negativo.') from exc
        if result < 0:
            raise ValidationError('ordem deve ser um inteiro não negativo.')
        return result

    def _values(self, row, type_row=False):
        name = row.get('nome', '')
        slug = row.get('slug') or slugify(name)
        if not name or not slug:
            raise ValidationError('nome e slug válido são obrigatórios.')
        values = {'nome': name, 'slug': slug, 'descricao': row.get('descricao', ''), 'ordem': self._order(row.get('ordem', '')), 'ativo': self._bool(row.get('ativo', ''), 'ativo')}
        if type_row:
            values.update(permite_segmento=self._bool(row.get('permite_segmento', ''), 'permite_segmento'), exige_segmento=self._bool(row.get('exige_segmento', ''), 'exige_segmento'))
        return values

    def _create(self, kind, model, lookup, values, report):
        scope = {} if model is CategoriaProduto else lookup
        conflict = model.objects.filter(Q(nome__iexact=values['nome']) | Q(slug=values['slug']), **scope).first()
        if conflict:
            if conflict.nome.casefold() != values['nome'].casefold() or conflict.slug != values['slug']:
                raise ValidationError(f'conflito de identidade com {conflict.nome!r} ({conflict.slug}).')
            if model is CategoriaProduto and conflict.setor_id != lookup['setor'].pk:
                report['conflitos'].append(
                    f'Categoria {conflict.slug}: setor atual '
                    f'{getattr(conflict.setor, "slug", None)!r}, setor proposto {lookup["setor"].slug!r}; '
                    'registro reutilizado sem remapeamento.'
                )
            report['ignorados'][kind] += 1
            report['duplicados'][kind] += 1
            return conflict
        candidate = model(**lookup, **values)
        candidate.full_clean()
        _, created = model.objects.get_or_create(**lookup, slug=values.pop('slug'), defaults=values)
        report['criados' if created else 'ignorados'][kind] += 1

    def _run(self, source, kind, callback, report):
        headers = self.HEADERS.get(kind) or self.EXTRA_HEADERS[kind]
        for line, row in self._rows(source, headers):
            try:
                callback(row)
            except (ValidationError, ValueError) as exc:
                messages = exc.messages if isinstance(exc, ValidationError) else [str(exc)]
                report['erros'].append(f'{kind}, linha {line}: {"; ".join(messages)}')

    def _import_setores(self, source, report):
        self._run(source, 'setores', lambda row: self._create('setores', SetorProduto, {}, self._values(row), report), report)

    def _import_categorias(self, source, report):
        def load(row):
            sector = SetorProduto.objects.filter(slug=row['setor_slug'], ativo=True).first()
            if not sector:
                raise ValidationError(f'setor inexistente ou inativo: {row["setor_slug"]!r}.')
            self._create('categorias', CategoriaProduto, {'setor': sector}, self._values(row), report)
        self._run(source, 'categorias', load, report)

    def _import_familias(self, source, report):
        def load(row):
            category = CategoriaProduto.objects.filter(slug=row['categoria_slug'], ativo=True, removido_em__isnull=True).first()
            if not category:
                raise ValidationError(f'categoria inexistente ou inativa: {row["categoria_slug"]!r}.')
            self._create('familias', FamiliaProduto, {'categoria': category}, self._values(row), report)
        self._run(source, 'familias', load, report)

    def _import_tipos(self, source, report):
        def load(row):
            category = CategoriaProduto.objects.filter(slug=row['categoria_slug'], ativo=True, removido_em__isnull=True).first()
            family = FamiliaProduto.objects.filter(categoria=category, slug=row['familia_slug'], ativo=True, removido_em__isnull=True).first()
            if not category:
                raise ValidationError(f'categoria inexistente ou inativa: {row["categoria_slug"]!r}.')
            if not family:
                raise ValidationError(f'família inexistente ou inativa: {row["familia_slug"]!r}.')
            self._create('tipos', TipoProduto, {'familia': family}, self._values(row, True), report)
        self._run(source, 'tipos', load, report)

    def _validate_extras(self, paths, report):
        context = {}
        for kind, path in paths.items():
            rows = list(self._rows(path, self.EXTRA_HEADERS[kind]))
            context[kind] = rows
        group_slugs = {row['slug'] for _, row in context.get('grupos_segmentos', [])}
        attribute_codes = {row['codigo'] for _, row in context.get('atributos', [])}
        for kind in ('segmentos', 'tipos_grupos', 'tipos_segmentos'):
            for line, row in context.get(kind, []):
                if group_slugs and row['grupo_slug'] not in group_slugs:
                    report['erros'].append(f'{kind}, linha {line}: grupo inexistente {row["grupo_slug"]!r}.')
        for line, row in context.get('opcoes_atributos', []):
            if attribute_codes and row['atributo_codigo'] not in attribute_codes:
                report['erros'].append(f'opcoes_atributos, linha {line}: atributo inexistente {row["atributo_codigo"]!r}.')
        report['validados'] = {kind: len(rows) for kind, rows in context.items()}
        return context

    def _import_segmentos(self, source, report):
        def load(row):
            values = self._values(row)
            self._create('segmentos', SegmentoProduto, {}, values, report)
        self._run(source, 'segmentos', load, report)

    def _import_tipos_segmentos(self, source, report):
        def load(row):
            family = FamiliaProduto.objects.filter(
                categoria__slug=row['categoria_slug'], slug=row['familia_slug'],
                ativo=True, removido_em__isnull=True,
            ).first()
            item = TipoProduto.objects.filter(
                familia=family, slug=row['tipo_slug'], ativo=True, removido_em__isnull=True,
            ).first()
            segment = SegmentoProduto.objects.filter(
                slug=row['segmento_slug'], ativo=True, removido_em__isnull=True,
            ).first()
            if not item or not segment:
                raise ValidationError('tipo ou segmento inexistente/inativo para o vínculo.')
            _, created = TipoProdutoSegmento.objects.get_or_create(
                tipo_produto=item, segmento=segment,
                defaults={'ativo': True, 'obrigatorio': row.get('obrigatorio', '').casefold() in {'sim','true','1'}},
            )
            report['criados' if created else 'ignorados']['tipos_segmentos'] += 1
        self._run(source, 'tipos_segmentos', load, report)

    def _report(self, report, dry_run, rolled_back):
        self.stdout.write(self.style.MIGRATE_HEADING('RELATÓRIO DA IMPORTAÇÃO DE TAXONOMIA'))
        for label, key in [('Criados', 'criados'), ('Ignorados', 'ignorados'), ('Duplicados', 'duplicados')]:
            self.stdout.write(f'{label}: {sum(report[key].values())}')
            for kind in self.HEADERS:
                self.stdout.write(f'  {kind.capitalize()}: {report[key][kind]}')
            for kind in ('segmentos', 'tipos_segmentos'):
                self.stdout.write(f'  {kind.capitalize()}: {report[key][kind]}')
        self.stdout.write(f'Erros: {len(report["erros"])}')
        for error in report['erros']:
            self.stdout.write(self.style.ERROR(f'  - {error}'))
        self.stdout.write(f'Conflitos de hierarquia: {len(report["conflitos"])}')
        for conflict in report['conflitos']:
            self.stdout.write(self.style.WARNING(f'  - {conflict}'))
        if report.get('validados'):
            self.stdout.write('Somente validados por ausência de model compatível:')
            for kind in ('grupos_segmentos', 'tipos_grupos', 'atributos', 'opcoes_atributos'):
                if kind in report['validados']:
                    self.stdout.write(f'  {kind}: {report["validados"][kind]}')
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run concluído: nenhuma alteração foi persistida.'))
        elif rolled_back:
            self.stdout.write(self.style.ERROR('Carga cancelada: toda a transação foi revertida.'))
        else:
            self.stdout.write(self.style.SUCCESS('Carga concluída com sucesso.'))
