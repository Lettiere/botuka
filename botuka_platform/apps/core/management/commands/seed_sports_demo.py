from apps.core.demo_seeds import seed_sports_demo
from ._demo_base import DemoSeedCommand
class Command(DemoSeedCommand):
    help="Popula estruturas esportivas fictícias locais."
    seed=staticmethod(seed_sports_demo)
