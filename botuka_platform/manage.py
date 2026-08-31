#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
        from apps.core.db_routing import database_executor
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    web_commands = {"runserver", "test", "check", "collectstatic", "findstatic"}
    database_commands = {
        "migrate", "showmigrations", "sqlmigrate", "flush", "dbshell",
        "dumpdata", "loaddata", "inspectdb",
    }
    alias = "worker" if command == "publicar_noticias_agendadas" else (
        "default" if command in web_commands else "maintenance"
    )

    if alias == "maintenance" and command in database_commands:
        has_database = any(
            argument == "--database" or argument.startswith("--database=")
            for argument in sys.argv[2:]
        )
        if not has_database:
            sys.argv.append("--database=maintenance")

    with database_executor(alias):
        execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
