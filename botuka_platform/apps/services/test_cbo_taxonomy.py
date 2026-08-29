from __future__ import annotations

import importlib
import tempfile
from pathlib import Path
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.migrations.operations.fields import AddField
from django.db.migrations.operations.models import AddConstraint, AddIndex, CreateModel
from django.test import SimpleTestCase, TestCase

from apps.services.cbo_catalog import import_catalog, load_catalog
from apps.services.models import (
    CBOFamilia,
    CBOGrandeGrupo,
    CBOOcupacao,
    CBOSinonimo,
    CBOSubgrupo,
    CBOSubgrupoPrincipal,
    Profissao,
    ProfissaoCBO,
    Setor,
)
from apps.services.taxonomy_rollout import load_rollout_lots, require_safe_profession


AUDIT_DIR = Path(__file__).resolve().parents[3] / '_auditoria_cbo'


def write_catalog(directory: Path, *, orphan_occupation=False):
    rows = {
        'cbo2002-grande-grupo.csv': [('1', 'Grande grupo')],
        'cbo2002-subgrupo-principal.csv': [('12', 'Subgrupo principal')],
        'cbo2002-subgrupo.csv': [('123', 'Subgrupo')],
        'cbo2002-familia.csv': [('1234', 'Família')],
        'cbo2002-ocupacao.csv': [('999956' if orphan_occupation else '123456', 'Ocupação')],
        'cbo2002-sinonimo.csv': [('999956' if orphan_occupation else '123456', 'Sinônimo')],
    }
    for filename, values in rows.items():
        content = 'CODIGO;TITULO\n' + ''.join(f'{code};{title}\n' for code, title in values)
        (directory / filename).write_text(content, encoding='cp1252')


class CBOCatalogTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        write_catalog(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def test_importacao_repetida_e_idempotente(self):
        catalog = load_catalog(self.directory)
        import_catalog(catalog)
        import_catalog(catalog)
        self.assertEqual(CBOGrandeGrupo.objects.count(), 1)
        self.assertEqual(CBOSubgrupoPrincipal.objects.count(), 1)
        self.assertEqual(CBOSubgrupo.objects.count(), 1)
        self.assertEqual(CBOFamilia.objects.count(), 1)
        self.assertEqual(CBOOcupacao.objects.count(), 1)
        self.assertEqual(CBOSinonimo.objects.count(), 1)

    def test_comando_em_dry_run_nao_escreve_no_banco(self):
        output = StringIO()
        call_command('importar_cbo_oficial', directory=self.directory, stdout=output)
        self.assertIn('banco não alterado', output.getvalue())
        self.assertEqual(CBOGrandeGrupo.objects.count(), 0)
        self.assertEqual(CBOOcupacao.objects.count(), 0)

    def test_codigo_oficial_duplicado_e_rejeitado(self):
        path = self.directory / 'cbo2002-ocupacao.csv'
        path.write_text(
            'CODIGO;TITULO\n123456;Ocupação\n123456;Outra ocupação\n',
            encoding='cp1252',
        )
        with self.assertRaisesMessage(ValidationError, 'Códigos duplicados'):
            load_catalog(self.directory)

    def test_validacao_rejeita_hierarquia_orfa(self):
        write_catalog(self.directory, orphan_occupation=True)
        with self.assertRaisesMessage(ValidationError, 'Ocupação órfão'):
            load_catalog(self.directory)

    def test_profissao_pode_permanecer_sem_cbo_e_uuid_e_preservado(self):
        setor = Setor.objects.create(nome='Setor de teste')
        profissao = Profissao.objects.create(nome='Profissão sem CBO', setor=setor)
        original_uuid = profissao.uuid
        self.assertFalse(profissao.ocupacoes_cbo.exists())
        profissao.refresh_from_db()
        self.assertEqual(profissao.uuid, original_uuid)

    def test_mesma_ocupacao_pode_ser_compartilhada_sem_reclassificar_profissao(self):
        catalog = load_catalog(self.directory)
        import_catalog(catalog)
        setor = Setor.objects.create(nome='Outro setor')
        primeira = Profissao.objects.create(nome='Primeira profissão', setor=setor)
        segunda = Profissao.objects.create(nome='Segunda profissão', setor=setor)
        ocupacao = CBOOcupacao.objects.get(codigo='123456')
        ProfissaoCBO.objects.create(profissao=primeira, ocupacao=ocupacao, principal=True)
        ProfissaoCBO.objects.create(profissao=segunda, ocupacao=ocupacao, principal=True)
        self.assertEqual(ocupacao.profissoes.count(), 2)
        self.assertEqual(primeira.setor_id, setor.id)
        self.assertEqual(segunda.setor_id, setor.id)


class RolloutSafetyTests(SimpleTestCase):
    def test_lotes_reais_sao_disjuntos_e_editorial_e_bloqueado(self):
        lots = load_rollout_lots(AUDIT_DIR)
        self.assertEqual(len(lots.safe), 2669)
        self.assertEqual(len(lots.editorial), 546)
        safe = require_safe_profession(lots.safe[0]['profissao_id'], lots)
        self.assertEqual(safe['status_homologacao'], 'HOMOLOGADO')
        with self.assertRaisesMessage(ValidationError, 'lote editorial'):
            require_safe_profession(lots.editorial[0]['profissao_id'], lots)

    def test_migration_de_schema_e_estritamente_aditiva(self):
        module = importlib.import_module(
            'apps.services.migrations.0009_cbofamilia_cbograndegrupo_cbosubgrupo_cboocupacao_and_more'
        )
        allowed = (CreateModel, AddField, AddIndex, AddConstraint)
        self.assertTrue(all(isinstance(operation, allowed) for operation in module.Migration.operations))
        serialized = ' '.join(str(operation).lower() for operation in module.Migration.operations)
        self.assertNotIn('servico.', serialized)
        self.assertNotIn('agendamento', serialized)
