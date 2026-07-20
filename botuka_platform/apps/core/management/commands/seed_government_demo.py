from apps.core.demo_seeds import seed_government_demo
from ._demo_base import DemoSeedCommand
class Command(DemoSeedCommand):
    help="Popula órgãos e ações públicas fictícias locais."
    seed=staticmethod(seed_government_demo)
