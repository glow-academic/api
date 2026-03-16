#!/bin/bash
set -euo pipefail

# Colors for Docker logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- CONFIG ----------------------------------------------------------
DB_USER=${POSTGRES_USER:-myuser}
DB_PASSWORD=${POSTGRES_PASSWORD:-mypassword}
DB_NAME=${POSTGRES_DB:-mydb}
HISTORY_DIR=${HISTORY_DIR:-/database/history}
DB_OPERATION=${DB_OPERATION:-}

# Normalize to lowercase
DB_OPERATION=$(echo "$DB_OPERATION" | tr '[:upper:]' '[:lower:]')

# --- LOGGING FUNCTIONS -----------------------------------------------
log_info() {
  echo -e "${CYAN}[DOCKER-DB]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[DOCKER-DB]${NC} $1"
}

log_warning() {
  echo -e "${YELLOW}[DOCKER-DB]${NC} $1"
}

log_error() {
  echo -e "${RED}[DOCKER-DB]${NC} $1"
}

# --- BACKUP FUNCTION -------------------------------------------------
backup_database() {
  log_info "Starting database backup on shutdown..."

  # Create history directory if it doesn't exist
  mkdir -p "$HISTORY_DIR"

  # Generate timestamp
  ts=$(date +%Y%m%d_%H%M%S)
  backup_file="$HISTORY_DIR/restore_${ts}.sql.gz"

  # Wait a moment for any ongoing transactions to complete
  sleep 2

  # Create compressed backup (custom format)
  log_info "Creating database backup: $backup_file"
  if pg_dump "postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}" -F c -f "$backup_file" 2>/dev/null; then
    log_success "Backup saved: $backup_file"

    # Keep only the last 10 backups to prevent disk space issues
    cd "$HISTORY_DIR"
    ls -t restore_*.sql.gz 2>/dev/null | tail -n +11 | xargs -r rm -- 2>/dev/null || true
    log_info "Cleaned up old backups (keeping last 10)"
  else
    log_warning "Backup failed or database not ready"
  fi

  log_success "Database backup completed"
}

# --- SIGNAL HANDLERS -------------------------------------------------
cleanup() {
  log_info "Received shutdown signal..."
  backup_database
  log_info "Shutting down PostgreSQL..."
  # Send SIGTERM to postgres process
  if [ -n "${PG_PID:-}" ]; then
    kill -TERM "$PG_PID" 2>/dev/null || true
    wait "$PG_PID" 2>/dev/null || true
  fi
  exit 0
}

# Trap signals that indicate shutdown
trap cleanup SIGTERM SIGINT SIGQUIT

# --- MAIN EXECUTION --------------------------------------------------
log_info "Starting Glow Database (Docker)"
log_info "DB_USER: $DB_USER"
log_info "DB_NAME: $DB_NAME"
log_info "DB_OPERATION: ${DB_OPERATION:-<unset>}"

# --- HANDLE DB_OPERATION MODES ---------------------------------------
case "$DB_OPERATION" in

  # ── skip (or empty/unset) ──────────────────────────────────────────
  ""|"skip")
    log_info "DB_OPERATION=$DB_OPERATION - Skipping initialization, using existing database"
    ;;

  # ── auto ───────────────────────────────────────────────────────────
  # Schema + seed on first start (empty data dir), preserve on restart.
  # Postgres naturally only runs init scripts on empty data dir.
  "auto")
    log_info "DB_OPERATION=auto - Schema + seed on first start, preserve on restart"
    log_info "Setting up database initialization..."

    mkdir -p /docker-entrypoint-initdb.d

    # Extensions init
    cat > /docker-entrypoint-initdb.d/00-glow-init.sql << 'EOF'
-- Glow Database Initialization Script
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
DO $$ BEGIN RAISE NOTICE 'Starting Glow database initialization...'; END $$;
EOF

    # Copy schema
    if [ -f /database/schema.sql ]; then
      log_info "Copying schema.sql to init directory..."
      cp /database/schema.sql /docker-entrypoint-initdb.d/10-schema.sql
      chmod 644 /docker-entrypoint-initdb.d/10-schema.sql
      chown postgres:postgres /docker-entrypoint-initdb.d/10-schema.sql
    else
      log_warning "schema.sql not found at /database/schema.sql"
    fi

    # Copy pre-built seed modules (if available)
    if [ -f /database/seeds/seed_modules.sql ]; then
      log_info "Copying seed_modules.sql to init directory..."
      cp /database/seeds/seed_modules.sql /docker-entrypoint-initdb.d/20-seed.sql
      chmod 644 /docker-entrypoint-initdb.d/20-seed.sql
      chown postgres:postgres /docker-entrypoint-initdb.d/20-seed.sql
    else
      log_info "No seed_modules.sql found - starting with schema only"
    fi
    ;;

  # ── modules ────────────────────────────────────────────────────────
  # Wipe data dir first, then load schema + seed (forced fresh start).
  "modules")
    log_info "DB_OPERATION=modules - Wiping data dir and rebuilding from schema + seed modules"
    log_warning "Cleaning database data directory..."
    rm -rf /var/lib/postgresql/data/18/*
    log_success "Database data directory cleaned."

    mkdir -p /docker-entrypoint-initdb.d

    # Extensions init
    cat > /docker-entrypoint-initdb.d/00-glow-init.sql << 'EOF'
-- Glow Database Initialization Script
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
DO $$ BEGIN RAISE NOTICE 'Starting Glow database initialization...'; END $$;
EOF

    # Copy schema
    if [ -f /database/schema.sql ]; then
      log_info "Copying schema.sql to init directory..."
      cp /database/schema.sql /docker-entrypoint-initdb.d/10-schema.sql
      chmod 644 /docker-entrypoint-initdb.d/10-schema.sql
      chown postgres:postgres /docker-entrypoint-initdb.d/10-schema.sql
    else
      log_error "schema.sql not found at /database/schema.sql - required for modules mode"
      exit 1
    fi

    # Copy pre-built seed modules
    if [ -f /database/seeds/seed_modules.sql ]; then
      log_info "Copying seed_modules.sql to init directory..."
      cp /database/seeds/seed_modules.sql /docker-entrypoint-initdb.d/20-seed.sql
      chmod 644 /docker-entrypoint-initdb.d/20-seed.sql
      chown postgres:postgres /docker-entrypoint-initdb.d/20-seed.sql
    else
      log_warning "No seed_modules.sql found - starting with schema only"
    fi
    ;;

  # ── restore ────────────────────────────────────────────────────────
  "restore")
    log_info "DB_OPERATION=restore - Looking for backup files..."

    mkdir -p /docker-entrypoint-initdb.d

    # Extensions init
    cat > /docker-entrypoint-initdb.d/00-glow-init.sql << 'EOF'
-- Glow Database Initialization Script
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
DO $$ BEGIN RAISE NOTICE 'Starting Glow database initialization...'; END $$;
EOF

    # Look for restore_*.sql.gz files in history volume
    if ls "$HISTORY_DIR"/restore_*.sql.gz 1> /dev/null 2>&1; then
      latest_backup=$(ls -t "$HISTORY_DIR"/restore_*.sql.gz 2>/dev/null | head -1)
      if [[ -n "$latest_backup" && -f "$latest_backup" ]]; then
        log_info "Found latest backup: $(basename "$latest_backup")"
        log_info "Setting up backup restoration..."

        if pg_restore -l "$latest_backup" > /dev/null 2>&1; then
          # Custom format backup - create a restore script
          log_info "Detected custom format backup, creating restore script..."
          backup_basename=$(basename "$latest_backup")
          cat > /docker-entrypoint-initdb.d/50-restore-backup.sh << EOF
#!/bin/bash
set -e
log_info() { echo -e "\${CYAN}[DOCKER-DB]\${NC} \$1"; }
log_warning() { echo -e "\${YELLOW}[DOCKER-DB]\${NC} \$1"; }
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info "Restoring from custom format backup: $backup_basename"
log_info "Executing: pg_restore -U $DB_USER -d $DB_NAME --no-owner --no-privileges --clean --if-exists $latest_backup"

RESTORE_EXIT=0
pg_restore -U "$DB_USER" -d $DB_NAME --no-owner --no-privileges --clean --if-exists "$latest_backup" 2>&1 | tee /tmp/pg_restore.log || RESTORE_EXIT=\$?

SCHEMA_ERROR_ONLY=\$(grep -c "schema \"public\" already exists" /tmp/pg_restore.log 2>/dev/null || echo "0")
if [ \$RESTORE_EXIT -ne 0 ] && [ "\$SCHEMA_ERROR_ONLY" -gt 0 ]; then
  log_warning "Schema creation error detected"
  OTHER_ERRORS=\$(grep -E "ERROR|FATAL" /tmp/pg_restore.log | grep -v "schema \"public\" already exists" | wc -l || echo "0")
  if [ "\$OTHER_ERRORS" -eq 0 ]; then
    log_info "Only schema creation error detected, treating as success..."
    RESTORE_EXIT=0
  fi
fi

if [ \$RESTORE_EXIT -ne 0 ]; then
  log_warning "pg_restore exited with code \$RESTORE_EXIT"
  log_warning "Continuing despite restore errors..."
else
  log_info "Backup restoration completed successfully"
fi
touch /var/lib/postgresql/.restore_complete 2>/dev/null || true
EOF
          chmod +x /docker-entrypoint-initdb.d/50-restore-backup.sh
          log_success "Custom format restore script prepared"
        elif gunzip -c "$latest_backup" > /docker-entrypoint-initdb.d/50-restore-backup.sql 2>/dev/null; then
          log_success "Plain SQL backup decompressed and prepared for restoration"
        else
          log_error "Failed to process backup file: $latest_backup"
          exit 1
        fi
      else
        log_error "No backup file found in $HISTORY_DIR"
        exit 1
      fi
    else
      log_error "No restore_*.sql.gz files found in $HISTORY_DIR"
      exit 1
    fi
    ;;

  # ── invalid ────────────────────────────────────────────────────────
  *)
    log_error "Invalid DB_OPERATION value: $DB_OPERATION"
    log_error "Valid values are:"
    log_error "  - auto:    Schema + seed on first start, preserve on restart (default)"
    log_error "  - modules: Wipe and rebuild from schema + seed modules"
    log_error "  - restore: Restore from latest backup"
    log_error "  - skip:    Use existing database (no init)"
    exit 1
    ;;
esac

# --- FINALIZATION SCRIPT ---------------------------------------------
if [ "$DB_OPERATION" != "" ] && [ "$DB_OPERATION" != "skip" ]; then
  # Create keycloak schema (Keycloak's Liquibase manages the actual tables).
  cat > /docker-entrypoint-initdb.d/15-keycloak-stub.sql << 'EOF'
CREATE SCHEMA IF NOT EXISTS keycloak;
EOF

  cat > /docker-entrypoint-initdb.d/99-finalize.sql << 'EOF'
-- Finalization Script
DO $$
BEGIN
    RAISE NOTICE 'Glow database initialization completed successfully!';
    RAISE NOTICE 'Database is ready for connections';
END $$;
EOF

  cat > /docker-entrypoint-initdb.d/99-mark-ready.sh << 'EOF'
#!/bin/bash
touch /var/lib/postgresql/.restore_complete 2>/dev/null || true
echo "[DB] Database initialization marked as complete at $(date)"
EOF
  chmod +x /docker-entrypoint-initdb.d/99-mark-ready.sh

  log_success "Database initialization scripts prepared"
fi

# --- START POSTGRESQL ------------------------------------------------
log_info "Starting PostgreSQL server..."

# Start PostgreSQL in the background so we can handle signals
docker-entrypoint.sh "$@" &
PG_PID=$!

log_success "PostgreSQL started with PID: $PG_PID"

# Wait for PostgreSQL to be ready
log_info "Waiting for PostgreSQL to be ready..."
until pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; do
  sleep 1
done

log_success "PostgreSQL is ready"

# Wait for initialization scripts to complete
sleep 3

log_success "Database is ready!"

# Wait for PostgreSQL process
wait "$PG_PID"
