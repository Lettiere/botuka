from contextlib import contextmanager
from contextvars import ContextVar

EXECUTOR_ALIASES = frozenset({"default", "worker", "internal", "maintenance"})
_current_executor = ContextVar("botuka_database_executor", default="default")


def current_executor():
    return _current_executor.get()


@contextmanager
def database_executor(alias):
    if alias not in EXECUTOR_ALIASES:
        raise ValueError(f"Executor de banco inválido: {alias}")
    token = _current_executor.set(alias)
    try:
        yield alias
    finally:
        _current_executor.reset(token)


class ExecutorDatabaseRouter:
    """Roteia toda operação ORM para o executor explicitamente ativo."""

    def db_for_read(self, model, **hints):
        return current_executor()

    def db_for_write(self, model, **hints):
        return current_executor()

    def allow_relation(self, obj1, obj2, **hints):
        database_1 = getattr(obj1._state, "db", None)
        database_2 = getattr(obj2._state, "db", None)
        if database_1 in EXECUTOR_ALIASES and database_2 in EXECUTOR_ALIASES:
            return database_1 == database_2
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == current_executor()
