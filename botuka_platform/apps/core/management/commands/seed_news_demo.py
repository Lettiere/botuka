from apps.core.demo_seeds import seed_news_demo
from ._demo_base import DemoSeedCommand
class Command(DemoSeedCommand):
    help="Popula artigos jornalísticos fictícios locais."
    seed=staticmethod(seed_news_demo)
