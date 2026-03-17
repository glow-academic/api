#!/bin/bash
set -euo pipefail

# =====================================================================
# Glow Database Docker Entrypoint
#
# DB_BACKUP env var controls initialization:
#   DB_BACKUP=fresh.sql.gz       Restore history/fresh.sql.gz
#   DB_BACKUP=university.sql.gz  Restore history/university.sql.gz
#   DB_BACKUP=                   Use existing database (default)
# =====================================================================

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DB_USER=${POSTGRES_USER:-myuser}
DB_PASSWORD=${POSTGRES_PASSWORD:-mypassword}
DB_NAME=${POSTGRES_DB:-mydb}
HISTORY_DIR=${HISTORY_DIR:-/database/history}
DB_BACKUP=${DB_BACKUP:-}
PGDATA=${PGDATA:-/var/lib/postgresql/data}

log_info()    { echo -e "${CYAN}[DOCKER-DB]${NC} $1"; }
log_success() { echo -e "${GREEN}[DOCKER-DB]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[DOCKER-DB]${NC} $1"; }
log_error()   { echo -e "${RED}[DOCKER-DB]${NC} $1"; }

# --- SIGNAL HANDLERS ------------------------------------------------
cleanup() {
  log_info "Received shutdown signal..."
  if [ -n "${PG_PID:-}" ]; then
    kill -TERM "$PG_PID" 2>/dev/null || true
    wait "$PG_PID" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup SIGTERM SIGINT SIGQUIT

# --- MAIN ------------------------------------------------------------
log_info "Starting Glow Database (Docker)"
log_info "DB_NAME: $DB_NAME"
log_info "DB_BACKUP: ${DB_BACKUP:-<unset>}"

if [[ -n "$DB_BACKUP" ]]; then
  BACKUP_FILE="$HISTORY_DIR/$DB_BACKUP"

  if [[ ! -f "$BACKUP_FILE" ]]; then
    log_error "Backup not found: $BACKUP_FILE"
    ls "$HISTORY_DIR"/*.sql.gz "$HISTORY_DIR"/*.sql 2>/dev/null | while read f; do
      log_info "  Available: $(basename "$f")"
    done
    exit 1
  fi

  log_info "Will restore from: $DB_BACKUP"

  # Wipe data dir so Postgres runs init scripts on fresh start
  rm -rf "$PGDATA"/*

  mkdir -p /docker-entrypoint-initdb.d

  # Restore script
  if [[ "$BACKUP_FILE" == *.gz ]]; then
    log_info "Decompressing backup..."
    gunzip -c "$BACKUP_FILE" > /docker-entrypoint-initdb.d/10-restore.sql
  else
    cp "$BACKUP_FILE" /docker-entrypoint-initdb.d/10-restore.sql
  fi
  chmod 644 /docker-entrypoint-initdb.d/10-restore.sql

  # Mark restore complete
  cat > /docker-entrypoint-initdb.d/99-mark-ready.sh << 'EOF'
#!/bin/bash
touch /var/lib/postgresql/.restore_complete 2>/dev/null || true
echo "[DB] Restore complete at $(date)"
EOF
  chmod +x /docker-entrypoint-initdb.d/99-mark-ready.sh

  log_success "Restore scripts prepared"
else
  # Check if this is a first start (empty data dir) — error if so
  if [[ ! -d "$PGDATA/base" ]]; then
    log_error "No existing database and DB_BACKUP is not set."
    log_error ""
    log_error "Set DB_BACKUP to a file in history/:"
    ls "$HISTORY_DIR"/*.sql.gz "$HISTORY_DIR"/*.sql 2>/dev/null | while read f; do
      log_error "  $(basename "$f")"
    done
    exit 1
  fi
  log_info "No DB_BACKUP set — using existing database"
fi

# --- START POSTGRESQL ------------------------------------------------
log_info "Starting PostgreSQL server..."
docker-entrypoint.sh "$@" &
PG_PID=$!

until pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; do
  sleep 1
done

sleep 3

# If restoring from backup, drop keycloak schema so Keycloak recreates it
# fresh via Liquibase. The backup includes keycloak tables but not Liquibase
# changelog records, causing "relation already exists" errors.
if [[ -n "$DB_BACKUP" ]]; then
  log_info "Dropping keycloak schema (will be recreated by Keycloak)..."
  psql -U "$DB_USER" -d "$DB_NAME" -c "DROP SCHEMA IF EXISTS keycloak CASCADE;" 2>/dev/null || true
fi

# Ensure keycloak schema exists (empty for Keycloak to populate)
psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE SCHEMA IF NOT EXISTS keycloak;" 2>/dev/null || true

log_success "Database is ready!"
wait "$PG_PID"
