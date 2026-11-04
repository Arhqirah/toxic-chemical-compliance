#!/bin/bash
# Creates the app's database account with the MINIMUM rights it needs.
# This is a .sh file (not .sql) so it can read the password from the
# environment instead of having it written in git.
set -e

mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" <<SQL
CREATE USER '${DB_APP_USER}'@'%' IDENTIFIED BY '${DB_APP_PASSWORD}';

-- Read-only tables
GRANT SELECT ON ${MARIADB_DATABASE}.site      TO '${DB_APP_USER}'@'%';
GRANT SELECT ON ${MARIADB_DATABASE}.warehouse TO '${DB_APP_USER}'@'%';
GRANT SELECT ON ${MARIADB_DATABASE}.users     TO '${DB_APP_USER}'@'%';

-- Stock changes on every delivery and dispatch
GRANT SELECT, INSERT, UPDATE, DELETE ON ${MARIADB_DATABASE}.stock TO '${DB_APP_USER}'@'%';

-- Jobs are created and later confirmed, never deleted
GRANT SELECT, INSERT, UPDATE ON ${MARIADB_DATABASE}.job TO '${DB_APP_USER}'@'%';

-- Audit log is append-only: no UPDATE, no DELETE
GRANT SELECT, INSERT ON ${MARIADB_DATABASE}.audit_log TO '${DB_APP_USER}'@'%';

FLUSH PRIVILEGES;
SQL
