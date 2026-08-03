import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import CommandError, call_command
from django.test import TestCase

from .models import CategoriaProduto, FamiliaProduto, TipoProduto


class TaxonomyImportCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = CategoriaProduto.objects.create(
            nome='Categoria para importação', slug='categoria-importacao',
        )

    def write_csv(self, directory, name, headers, rows):
        path = Path(directory) / name
        with path.open('w', encoding='utf-8', newline='') as target:
            writer = csv.DictWriter(target, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def family_csv(self, directory, **overrides):
        row = {
            'categoria_slug': self.category.slug, 'nome': 'Família importada',
            'slug': 'familia-importada', 'descricao': 'Descrição',
            'ordem': '10', 'ativo': 'sim',
        }
        row.update(overrides)
        return self.write_csv(
            directory, 'familias.csv',
            ['categoria_slug', 'nome', 'slug', 'descricao', 'ordem', 'ativo'], [row],
        )

    def type_csv(self, directory, **overrides):
        row = {
            'categoria_slug': self.category.slug,
            'familia_slug': 'familia-importada', 'nome': 'Tipo importado',
            'slug': 'tipo-importado', 'descricao': 'Descrição', 'ordem': '20',
            'permite_segmento': 'não', 'exige_segmento': 'não', 'ativo': 'sim',
        }
        row.update(overrides)
        return self.write_csv(
            directory, 'tipos.csv',
            [
                'categoria_slug', 'familia_slug', 'nome', 'slug', 'descricao',
                'ordem', 'permite_segmento', 'exige_segmento', 'ativo',
            ], [row],
        )

    def test_dry_run_validates_and_rolls_back(self):
        with TemporaryDirectory() as directory:
            family = self.family_csv(directory)
            output = StringIO()
            call_command(
                'importar_taxonomia_produtos', familias=family,
                dry_run=True, stdout=output,
            )
        self.assertFalse(FamiliaProduto.objects.filter(slug='familia-importada').exists())
        self.assertIn('nenhuma alteração foi persistida', output.getvalue())

    def test_import_is_atomic_and_idempotent(self):
        with TemporaryDirectory() as directory:
            family = self.family_csv(directory)
            product_type = self.type_csv(directory)
            call_command(
                'importar_taxonomia_produtos', familias=family, tipos=product_type,
                aplicar=True, stdout=StringIO(),
            )
            output = StringIO()
            call_command(
                'importar_taxonomia_produtos', familias=family, tipos=product_type,
                aplicar=True, stdout=output,
            )
        self.assertEqual(FamiliaProduto.objects.filter(slug='familia-importada').count(), 1)
        self.assertEqual(TipoProduto.objects.filter(slug='tipo-importado').count(), 1)
        self.assertIn('Ignorados: 2', output.getvalue())

    def test_any_invalid_row_rolls_back_everything(self):
        with TemporaryDirectory() as directory:
            family = self.family_csv(directory)
            product_type = self.type_csv(directory, exige_segmento='sim')
            with self.assertRaises(CommandError):
                call_command(
                    'importar_taxonomia_produtos', familias=family, tipos=product_type,
                    aplicar=True, stdout=StringIO(), stderr=StringIO(),
                )
        self.assertFalse(FamiliaProduto.objects.filter(slug='familia-importada').exists())
        self.assertFalse(TipoProduto.objects.filter(slug='tipo-importado').exists())
