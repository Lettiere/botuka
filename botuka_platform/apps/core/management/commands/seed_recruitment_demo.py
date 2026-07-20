from apps.core.demo_seeds import seed_recruitment_demo
from ._demo_base import DemoSeedCommand
class Command(DemoSeedCommand):
    help="Popula vagas e currículos fictícios locais."
    seed=staticmethod(seed_recruitment_demo)
