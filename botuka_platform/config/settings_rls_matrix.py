import os

from .settings import *  # noqa: F401,F403

# A instrumentação usa exclusivamente um banco de teste criado pela role maintenance.
os.environ["BOTUKA_DEMO_DATABASES"] = "test_botuka1_rls_matrix"
ALLOWED_HOSTS = [*ALLOWED_HOSTS, "botuka.com.br"]
_maintenance = DATABASES["maintenance"]
for _alias in ("default", "worker", "internal", "maintenance"):
    DATABASES[_alias] = {
        **DATABASES[_alias],
        "USER": _maintenance["USER"],
        "PASSWORD": _maintenance["PASSWORD"],
    }

DATABASES["default"]["TEST"] = {"NAME": "test_botuka1_rls_matrix"}
for _alias in ("worker", "internal", "maintenance"):
    DATABASES[_alias]["TEST"] = {"MIRROR": "default"}

TEST_RUNNER = "apps.core.rls_matrix_runner.RLSMatrixTestRunner"
DATABASE_ROUTERS = ["apps.core.rls_matrix_runner.MatrixPhysicalRouter"]

# Nos testes instrumentados, os executores continuam lógicos, mas toda a suíte
# usa uma única conexão física. Isso preserva o isolamento transacional nativo
# de TestCase/SimpleTestCase e evita que aliases espelhados enxerguem estados
# intermediários diferentes.
MIDDLEWARE = [
    "apps.core.rls_matrix_runner.MatrixDatabaseExecutorMiddleware"
    if item == "apps.core.db_middleware.DatabaseExecutorMiddleware"
    else "apps.core.rls_matrix_runner.MatrixRLSUserContextMiddleware"
    if item == "apps.core.rls_middleware.RLSUserContextMiddleware"
    else item
    for item in MIDDLEWARE
]
