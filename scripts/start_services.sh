#!/usr/bin/env bash
set -e
cd /home/botuka/htdocs/botuka.com.br/botuka_services
exec /home/botuka/htdocs/botuka.com.br/.venv_linux/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:7701 \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
