from apps.core.demo_seeds import seed_home_demo
from ._demo_base import DemoSeedCommand
class Command(DemoSeedCommand):
    help="Popula todos os dados demonstrativos consumidos pela HOME local."
    seed=staticmethod(seed_home_demo)
