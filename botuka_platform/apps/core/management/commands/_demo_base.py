from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.base import BaseCommand
from apps.core.demo_seeds import assert_demo_database


class DemoSeedCommand(BaseCommand):
    seed = None

    def handle(self, *args, **options):
        if not settings.DEBUG or str(getattr(settings, "APP_ENV", "")).lower() == "production":
            raise CommandError("Este comando é exclusivo do ambiente local com DEBUG ativo.")
        try:
            assert_demo_database()
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        resultado = self.seed()
        self.stdout.write(self.style.SUCCESS(", ".join(f"{k}={v}" for k, v in resultado.items())))
