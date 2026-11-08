#!/bin/bash
# Nightly database backup (including the audit log).
#
# Dumps the whole toxic_chemical database from the running db container
# into ~/backups as a compressed .sql.gz file, and deletes backups older
# than KEEP_DAYS. Run by cron as the deploy user (see README).
#
# Restore a backup:
#   gunzip -c ~/backups/toxic_chemical_2026-11-08_0230.sql.gz \
#     | docker compose exec -T db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"'
set -euo pipefail

KEEP_DAYS=7
BACKUP_DIR="$HOME/backups"
STAMP=$(date +%Y-%m-%d_%H%M)
FILE="$BACKUP_DIR/toxic_chemical_$STAMP.sql.gz"
# If anything fails, don't leave a half-written file behind
trap 'rm -f "$FILE.tmp"' EXIT

# docker compose must run from the project folder (where docker-compose.yml is)
cd "$(dirname "$0")/.."
mkdir -p "$BACKUP_DIR"

# --single-transaction: a consistent snapshot without locking the tables,
#   so the app keeps working while the backup runs.
# The root password is read INSIDE the container from its own environment,
#   so it never appears in this script or in the process list on the host.
docker compose exec -T db sh -c \
  'mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction --routines --databases "$MARIADB_DATABASE"' \
  | gzip > "$FILE.tmp"

# Only keep the file if the dump finished (the last line of a complete dump is "-- Dump completed")
if gunzip -c "$FILE.tmp" | tail -n 1 | grep -q "Dump completed"; then
  mv "$FILE.tmp" "$FILE"
  echo "$(date '+%F %T') OK   $FILE ($(du -h "$FILE" | cut -f1))"
else
  rm -f "$FILE.tmp"
  echo "$(date '+%F %T') FAIL backup was incomplete and has been discarded" >&2
  exit 1
fi

# Delete backups older than KEEP_DAYS days
find "$BACKUP_DIR" -name 'toxic_chemical_*.sql.gz' -mtime +"$KEEP_DAYS" -delete
