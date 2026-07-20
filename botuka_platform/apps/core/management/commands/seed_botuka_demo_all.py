from apps.core.demo_seeds import seed_home_demo
from ._demo_base import DemoSeedCommand
class Command(DemoSeedCommand):
    help="Popula de forma idempotente todos os módulos demonstrativos locais."
    seed=staticmethod(seed_home_demo)
