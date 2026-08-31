from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import SimpleTestCase

from apps.core.db_middleware import request_database_alias
from apps.core.db_routing import ExecutorDatabaseRouter, current_executor, database_executor
from apps.core.rls_context import rls_user_context
from apps.core.rls_middleware import RLSUserContextMiddleware


class RLSUserContextMiddlewareTests(SimpleTestCase):
    @patch("apps.core.rls_middleware.connections")
    def test_non_postgresql_is_a_noop(self, connections):
        connection = connections.__getitem__.return_value
        connection.vendor = "sqlite"
        response = HttpResponse("ok")
        get_response = MagicMock(return_value=response)

        result = RLSUserContextMiddleware(get_response)(SimpleNamespace())

        self.assertIs(result, response)
        connection.cursor.assert_not_called()

    @patch("apps.core.rls_middleware.transaction")
    @patch("apps.core.rls_middleware.connections")
    def test_authenticated_identity_comes_only_from_request_user(
        self, connections, transaction
    ):
        connection = connections.__getitem__.return_value
        connection.vendor = "postgresql"
        cursor = connection.cursor.return_value.__enter__.return_value
        request = SimpleNamespace(
            user=SimpleNamespace(pk=42, is_authenticated=True),
            POST={"usuario_id": "999"},
        )

        RLSUserContextMiddleware(lambda request: HttpResponse("ok"))(request)

        connections.__getitem__.assert_called_with("default")
        transaction.atomic.assert_called_once_with(using="default")
        cursor.execute.assert_called_once_with(
            "SELECT set_config('app.user_id', %s, true)", ["42"]
        )

    @patch("apps.core.rls_middleware.transaction")
    @patch("apps.core.rls_middleware.connections")
    def test_anonymous_request_sets_empty_identity(self, connections, transaction):
        connection = connections.__getitem__.return_value
        connection.vendor = "postgresql"
        cursor = connection.cursor.return_value.__enter__.return_value
        request = SimpleNamespace(
            user=SimpleNamespace(pk=None, is_authenticated=False)
        )

        RLSUserContextMiddleware(lambda request: HttpResponse("ok"))(request)

        cursor.execute.assert_called_once_with(
            "SELECT set_config('app.user_id', %s, true)", [""]
        )

    @patch("apps.core.rls_middleware.transaction")
    @patch("apps.core.rls_middleware.connections")
    def test_error_response_marks_transaction_for_rollback(
        self, connections, transaction
    ):
        connection = connections.__getitem__.return_value
        connection.vendor = "postgresql"
        request = SimpleNamespace(user=None)

        RLSUserContextMiddleware(
            lambda request: HttpResponse(status=403)
        )(request)

        transaction.set_rollback.assert_called_once_with(True, using="default")

    @patch("apps.core.rls_middleware.transaction")
    @patch("apps.core.rls_middleware.connections")
    def test_exception_marks_active_transaction_for_rollback(
        self, connections, transaction
    ):
        connection = connections.__getitem__.return_value
        connection.vendor = "postgresql"
        connection.in_atomic_block = True
        middleware = RLSUserContextMiddleware(lambda request: None)

        result = middleware.process_exception(
            SimpleNamespace(), RuntimeError("failure")
        )

        self.assertIsNone(result)
        transaction.set_rollback.assert_called_once_with(True, using="default")


class ExecutorRoutingTests(SimpleTestCase):
    def test_context_is_explicit_and_restored(self):
        self.assertEqual(current_executor(), "default")
        with database_executor("worker"):
            self.assertEqual(current_executor(), "worker")
            self.assertEqual(ExecutorDatabaseRouter().db_for_read(object), "worker")
            self.assertEqual(ExecutorDatabaseRouter().db_for_write(object), "worker")
        self.assertEqual(current_executor(), "default")

    def test_internal_paths_are_routed_without_prefix_ambiguity(self):
        self.assertEqual(request_database_alias("/admin/"), "internal")
        self.assertEqual(request_database_alias("/gestao/comunicacao/"), "internal")
        self.assertEqual(request_database_alias("/agenda/"), "default")


class RLSUserContextTests(SimpleTestCase):
    @patch("apps.core.rls_context.transaction")
    @patch("apps.core.rls_context.connection")
    def test_postgresql_context_is_transaction_local(self, connection, transaction):
        connection.vendor = "postgresql"
        cursor = connection.cursor.return_value.__enter__.return_value

        with rls_user_context(73):
            pass

        transaction.atomic.assert_called_once_with()
        cursor.execute.assert_called_once_with(
            "SELECT set_config('app.user_id', %s, true)", ["73"]
        )

    @patch("apps.core.rls_context.connection")
    def test_non_postgresql_context_is_a_noop(self, connection):
        connection.vendor = "sqlite"

        with rls_user_context(73):
            pass

        connection.cursor.assert_not_called()


class ExistingRLSPolicyMigrationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "social"
            / "migrations"
            / "0007_rls_policies.py"
        )
        cls.sql = migration_path.read_text(encoding="utf-8")

    def test_existing_policy_names_are_preserved(self):
        for policy in (
            "social_post_save_owner_policy",
            "social_block_select_policy",
            "social_block_insert_policy",
            "social_block_delete_policy",
        ):
            self.assertIn(policy, self.sql)

    def test_policies_use_runtime_role_and_transaction_identity(self):
        self.assertIn("TO botuka_app", self.sql)
        self.assertIn("current_setting('app.user_id', true)", self.sql)

    def test_migration_never_forces_rls(self):
        self.assertNotIn("FORCE ROW LEVEL SECURITY", self.sql.upper())

    def test_reverse_disables_rls_and_drops_every_policy(self):
        self.assertEqual(self.sql.count("DISABLE ROW LEVEL SECURITY"), 2)
        self.assertEqual(self.sql.count("DROP POLICY IF EXISTS"), 4)
