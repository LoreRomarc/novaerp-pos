#!/usr/bin/env bash
# Build reproducible para Render u otro proveedor Linux.
set -o errexit

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
# Catálogo inicial e incrementos definidos en el archivo versionado. El comando
# es idempotente: sólo crea productos/variantes faltantes, por lo que puede
# ejecutarse en cada despliegue sin duplicar ni reescribir el historial.
python manage.py cargar_catalogo_productos
python manage.py check --deploy
