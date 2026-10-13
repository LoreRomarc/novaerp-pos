#!/usr/bin/env bash
set -Eeuo pipefail

# Se ejecuta en el VPS. La contraseña se lee de /etc/novaerp/novaerp.env;
# nunca se escribe en este archivo ni se versiona en Git.
set -a
source /etc/novaerp/novaerp.env
set +a

BACKUP_DIR=/var/backups/novaerp
STAMP=$(date +%F_%H%M%S)
mkdir -p "$BACKUP_DIR"
export PGPASSWORD="$POSTGRES_PASSWORD"
pg_dump -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$BACKUP_DIR/novaerp_${STAMP}.dump"

# Conserva los últimos 14 respaldos locales. Además configure una copia
# cifrada fuera del VPS (por ejemplo, almacenamiento de la empresa).
find "$BACKUP_DIR" -type f -name 'novaerp_*.dump' -mtime +14 -delete
