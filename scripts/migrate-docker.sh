#!/bin/bash
# Run database migrations inside Docker.
#
# Migration files are named: v{version}_{number}_{description}.sql
#   e.g., v0.2.0_01_add_widget.sql
#
# The `migrations.applied` table tracks what's been applied. This script only
# applies files not yet recorded — safe to run repeatedly.
#
# Usage:
#   ./scripts/migrate-docker.sh          # Apply all pending add migrations
#   ./scripts/migrate-docker.sh add      # Same
#   ./scripts/migrate-docker.sh remove   # Apply pending remove migrations

set -e

MIGRATION_TYPE="${1:-add}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

DB_USER="${DB_USER:-myuser}"
DB_NAME="${DB_NAME:-mydb}"

DCEXEC="docker compose exec -T database"

# Ensure database is running and healthy
docker compose up -d database pgbouncer
echo "Waiting for database to be healthy..."
timeout 120 bash -c "until docker compose exec -T database pg_isready -U \"$DB_USER\" -d \"$DB_NAME\" 2>/dev/null; do sleep 3; done"

# Ensure migrations schema and table exist
$DCEXEC psql -U "$DB_USER" -d "$DB_NAME" -c "
CREATE SCHEMA IF NOT EXISTS migrations;
CREATE TABLE IF NOT EXISTS migrations.applied (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(20) NOT NULL,
    number INTEGER NOT NULL,
    type VARCHAR(10) NOT NULL DEFAULT 'add' CHECK (type IN ('add', 'remove')),
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT migrations_unique UNIQUE (version, number, type)
);" 2>/dev/null

apply_migrations() {
  local mtype="$1"
  local mdir="database/migrate/$mtype"
  local applied=0
  local skipped=0

  if [ ! -d "$mdir" ]; then
    echo "No $mtype migration directory found"
    return 0
  fi

  for sql_file in "$mdir"/v*.sql; do
    [ -f "$sql_file" ] || continue

    local filename
    filename=$(basename "$sql_file")

    # Parse version and number from filename: v0.2.0_01_description.sql
    local version number
    version=$(echo "$filename" | sed -E 's/^(v[0-9]+\.[0-9]+\.[0-9]+)_.*/\1/')
    number=$(echo "$filename" | sed -E 's/^v[0-9]+\.[0-9]+\.[0-9]+_([0-9]+)_.*/\1/')

    if [ -z "$version" ] || [ -z "$number" ]; then
      echo "Skipping: $filename (could not parse version/number)"
      continue
    fi

    # Check if already applied
    local already
    already=$($DCEXEC psql -U "$DB_USER" -d "$DB_NAME" -tAc \
      "SELECT COUNT(*) FROM migrations.applied WHERE version='$version' AND number=$number AND type='$mtype';" 2>/dev/null | tr -d '[:space:]' || echo "0")
    if [ "$already" -gt 0 ] 2>/dev/null; then
      skipped=$((skipped + 1))
      continue
    fi

    echo "Applying: $filename"
    $DCEXEC psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < "$sql_file" || {
      echo "Migration failed: $filename"
      exit 1
    }

    # Record as applied
    $DCEXEC psql -U "$DB_USER" -d "$DB_NAME" -c \
      "INSERT INTO migrations.applied (version, number, type, name) VALUES ('$version', $number, '$mtype', '$filename') ON CONFLICT DO NOTHING;" 2>/dev/null

    applied=$((applied + 1))
  done

  echo "$mtype migrations: $applied applied, $skipped already applied"
}

echo "Applying $MIGRATION_TYPE migrations..."
apply_migrations "$MIGRATION_TYPE"
