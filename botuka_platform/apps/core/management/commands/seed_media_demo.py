from apps.core.demo_seeds import seed_media_demo
from ._demo_base import DemoSeedCommand
class Command(DemoSeedCommand):
    help="Popula o catálogo fictício da YTv Botuka local."
    seed=staticmethod(seed_media_demo)
