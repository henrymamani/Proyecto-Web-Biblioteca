#!/usr/bin/env bash
set -o errexit

# Los archivos secretos de Render, incluido el certificado CA de Aiven,
# están disponibles al iniciar el servicio.
python manage.py migrate --no-input
exec python -m gunicorn Biblioteca_sis.wsgi:application
