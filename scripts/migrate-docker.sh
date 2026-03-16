#!/bin/bash
# Run database migrations inside Docker via docker compose exec.
#
# Usage:
#   ./scripts/migrate-docker.sh add      # Apply add migrations only (pre-deploy)
#   ./scripts/migrate-docker.sh remove   # Apply remove migrations only (post-deploy)
#   ./scripts/migrate-docker.sh all      # Apply both add then remove

set -e

MIGRATION_TYPE="${1:-all}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

# Load .env if it exists
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

DB_USER="${DB_USER:-myuser}"
DB_NAME="${DB_NAME:-mydb}"

DCEXEC="docker compose exec -T database"

# Ensure database is running and healthy
docker compose up -d database pgbouncer
echo "Waiting for database to be healthy..."
timeout 120 bash -c "until docker compose exec -T database pg_isready -U \"$DB_USER\" -d \"$DB_NAME\" 2>/dev/null; do sleep 3; done"

# Check if migration_tracking table exists
check_tracking() {
  $DCEXEC psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'migration_tracking');" 2>/dev/null | tr -d '[:space:]' || echo "f"
}

# Apply migrations for a given type (add or remove)
apply_migrations() {
  local mtype="$1"
  local mdir="database/migrate/$mtype"
  local has_tracking
  has_tracking=$(check_tracking)
  local applied=0
  local skipped=0

  if [ ! -d "$mdir" ]; then
    echo "No $mtype migration directory found"
    return 0
  fi

  for sql_file in "$mdir"/*.sql; do
    [ -f "$sql_file" ] || continue

    local migration_num
    migration_num=$(basename "$sql_file" | grep -oE '^[0-9]+')
    local migration_name
    migration_name=$(basename "$sql_file")

    # Skip if already tracked
    if [ "$has_tracking" = "t" ]; then
      local already
      already=$($DCEXEC psql -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT COUNT(*) FROM migration_tracking WHERE migration_number=$migration_num AND migration_type='$mtype';" 2>/dev/null | tr -d '[:space:]' || echo "0")
      if [ "$already" -gt 0 ] 2>/dev/null; then
        echo "Skipping: $migration_name (already applied)"
        skipped=$((skipped + 1))
        continue
      fi
    fi

    # For remove migrations, skip if corresponding add not applied
    if [ "$mtype" = "remove" ]; then
      if [ "$has_tracking" != "t" ]; then
        echo "No migration_tracking table — skipping remove migrations"
        return 0
      fi

      local add_applied
      add_applied=$($DCEXEC psql -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT COUNT(*) FROM migration_tracking WHERE migration_number=$migration_num AND migration_type='add';" 2>/dev/null | tr -d '[:space:]' || echo "0")
      if [ "$add_applied" -le 0 ] 2>/dev/null; then
        echo "Skipping: $migration_name (add migration not applied yet)"
        skipped=$((skipped + 1))
        continue
      fi

      # Skip empty/comment-only files
      if ! grep -qE '^[^-]' "$sql_file" 2>/dev/null; then
        echo "Skipping: $migration_name (no SQL statements)"
        skipped=$((skipped + 1))
        continue
      fi
    fi

    echo "Applying $mtype: $migration_name"
    $DCEXEC psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < "$sql_file" || {
      if [ "$mtype" = "remove" ]; then
        echo "Remove migration failed: $migration_name (non-fatal, continuing)"
        continue
      else
        echo "Migration failed: $migration_name"
        exit 1
      fi
    }

    # After migration 00, tracking table exists
    if [ "$migration_num" = "0" ] || [ "$migration_num" = "00" ]; then
      has_tracking="t"
    fi

    # Record in tracking table
    if [ "$has_tracking" = "t" ]; then
      $DCEXEC psql -U "$DB_USER" -d "$DB_NAME" -c \
        "INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES ($migration_num, '$migration_name', '$mtype') ON CONFLICT (migration_number, migration_type) DO NOTHING;" 2>/dev/null || true
    fi

    applied=$((applied + 1))
  done

  echo "$mtype migrations complete (applied: $applied, skipped: $skipped)"
}

case "$MIGRATION_TYPE" in
  add)
    echo "Applying add migrations..."
    apply_migrations add
    ;;
  remove)
    echo "Applying remove migrations..."
    apply_migrations remove
    ;;
  all)
    echo "Applying add migrations..."
    apply_migrations add
    echo "Applying remove migrations..."
    apply_migrations remove
    ;;
  *)
    echo "Usage: $0 [add|remove|all]"
    exit 1
    ;;
esac
