from apps.core.demo_seeds import seed_services_demo
from ._demo_base import DemoSeedCommand
class Command(DemoSeedCommand):
    help="Popula empresas e serviços fictícios locais."
    seed=staticmethod(seed_services_demo)
