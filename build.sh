#!/usr/bin/env bash
# Build reproducible para Render u otro proveedor Linux.
set -o errexit

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py check --deploy
