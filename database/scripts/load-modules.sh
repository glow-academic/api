#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Load Modular Seed Data
# =============================================================================
# Loads base-seed.sql and setup-specific seed files into the database.
#
# Usage:
#   ./load-modules.sh                  # Load seeds directly to psql
#   ./load-modules.sh --output         # Write to timestamped file
#   ./load-modules.sh --output out.sql # Write to specific file
#
# Environment:
#   SEED_SETUP  - "university" (default) or "organization"
# =============================================================================

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/../.." && pwd)"
modules_dir="$script_dir/../output"

# --- Parse args ---------------------------------------------------------------
output_mode=false
output_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      output_mode=true
      if [[ -n "${2:-}" && "${2:0:1}" != "-" ]]; then
        output_file="$2"
        shift
      fi
      ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

# --- Load .env ----------------------------------------------------------------
if [[ -f "$script_dir/../.env" ]]; then
  set -a
  source "$script_dir/../.env"
  set +a
fi

DB_USER=${DB_USER:-myuser}
DB_PASSWORD=${DB_PASSWORD:-mypassword}
DB_NAME=${DB_NAME:-mydb}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

SEED_SETUP=${SEED_SETUP:-university}

# --- Assemble SQL -------------------------------------------------------------
sql_parts=()

add_file() {
  local filepath=$1
  if [[ -f "$filepath" ]]; then
    sql_parts+=("$filepath")
  else
    echo "  WARNING: File not found: $filepath"
  fi
}

load_setup() {
  local setup_name=$1
  local seed_file="$modules_dir/setups/$setup_name/seed.sql"
  if [[ ! -f "$seed_file" ]]; then
    echo "  WARNING: seed.sql not found for setup '$setup_name'. Run: python -m database.scripts.runner --setup $setup_name"
    return
  fi
  echo "Loading setups/$setup_name/seed.sql ..."
  add_file "$seed_file"
}

echo ""
echo "=== Assembling seed SQL (setup: $SEED_SETUP) ==="
echo ""

# Base seed (resources, profiles, providers, models, agents, etc.)
base_seed="$modules_dir/base-seed.sql"
if [[ -f "$base_seed" ]]; then
  echo "Loading base-seed.sql ..."
  add_file "$base_seed"
else
  echo "ERROR: base-seed.sql not found. Run: python -m database.scripts.runner --modules"
  exit 1
fi

# Organization setup is always loaded
load_setup "organization"

# University setup is loaded only when SEED_SETUP=university
if [[ "$SEED_SETUP" == "university" ]]; then
  load_setup "university"
fi

echo ""
echo "Assembled ${#sql_parts[@]} module files"

if [[ ${#sql_parts[@]} -eq 0 ]]; then
  echo "WARNING: No module files found."
  exit 1
fi

# --- Output or execute --------------------------------------------------------
if $output_mode; then
  if [[ -z "$output_file" ]]; then
    timestamp=$(date +%Y%m%d_%H%M%S)
    output_file="$script_dir/../seeds/seed_modules_${timestamp}.sql"
  fi
  mkdir -p "$(dirname "$output_file")"

  {
    echo "-- Generated seed file from modular modules"
    echo "-- Setup: $SEED_SETUP"
    echo "-- Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "-- Files: ${#sql_parts[@]}"
    echo ""
    echo "DO \$\$ BEGIN EXECUTE 'SET session_replication_role = replica'; EXCEPTION WHEN insufficient_privilege THEN NULL; END \$\$;"
    echo ""
    for f in "${sql_parts[@]}"; do
      echo "-- ================================================================"
      echo "-- File: $(basename "$f")"
      echo "-- ================================================================"
      cat "$f"
      echo ""
    done
    echo ""
    echo "DO \$\$ BEGIN EXECUTE 'SET session_replication_role = DEFAULT'; EXCEPTION WHEN insufficient_privilege THEN NULL; END \$\$;"
  } > "$output_file"

  echo ""
  echo "Written to: $output_file"
else
  echo "Loading into database: $DB_NAME ..."
  {
    echo "DO \$\$ BEGIN EXECUTE 'SET session_replication_role = replica'; EXCEPTION WHEN insufficient_privilege THEN NULL; END \$\$;"
    for f in "${sql_parts[@]}"; do
      cat "$f"
      echo ""
    done
    echo "DO \$\$ BEGIN EXECUTE 'SET session_replication_role = DEFAULT'; EXCEPTION WHEN insufficient_privilege THEN NULL; END \$\$;"
  } | psql "$DB_URL" -v ON_ERROR_STOP=0 --quiet 2>&1 | grep -v "^$" || true

  # Copy upload files to the project uploads directory
  uploads_dir="$project_root/uploads"
  for setup_name in organization university; do
    uploads_files_dir="$modules_dir/setups/$setup_name/uploads/files"
    if [[ -d "$uploads_files_dir" ]]; then
      mkdir -p "$uploads_dir"
      echo "Copying upload files from $setup_name/uploads/files/ ..."
      cp -Rn "$uploads_files_dir"/ "$uploads_dir/" 2>/dev/null || true
    fi
  done

  # Refresh all unpopulated materialized views
  echo "Refreshing materialized views..."
  mv_count=$(psql "$DB_URL" -tAc "SELECT COUNT(*) FROM pg_matviews WHERE NOT ispopulated" 2>/dev/null || echo "0")
  if [[ "$mv_count" -gt 0 ]]; then
    psql "$DB_URL" -tAc "SELECT matviewname FROM pg_matviews WHERE NOT ispopulated" 2>/dev/null | while read -r mv; do
      psql "$DB_URL" --quiet -c "REFRESH MATERIALIZED VIEW \"$mv\"" 2>/dev/null
    done
    echo "  $mv_count MVs refreshed."
  else
    echo "  All MVs already populated."
  fi

  echo ""
  echo "=== Seed loading complete ==="
fi
