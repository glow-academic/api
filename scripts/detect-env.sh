#!/bin/bash
# Detect active/target environment and pending migration status.
# Outputs KEY=VALUE lines suitable for eval or GitHub Actions outputs.
#
# Usage:
#   eval $(./scripts/detect-env.sh)

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

# Load .env if it exists
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

ACTIVE_ENV="${ACTIVE_ENV:-blue}"
[ -z "$ACTIVE_ENV" ] && ACTIVE_ENV="blue"
if [ "$ACTIVE_ENV" = "green" ]; then
  TARGET_ENV="blue"
else
  TARGET_ENV="green"
fi

HAS_MIGRATIONS="false"
HAS_REMOVE_MIGRATIONS="false"

MIGRATE_ADD_DIR="database/migrate/add"
MIGRATE_REMOVE_DIR="database/migrate/remove"

if [ -d "$MIGRATE_ADD_DIR" ]; then
  ADD_COUNT=$(find "$MIGRATE_ADD_DIR" -name "*.sql" 2>/dev/null | wc -l | tr -d ' ')
else
  ADD_COUNT=0
fi

if [ -d "$MIGRATE_REMOVE_DIR" ]; then
  REMOVE_COUNT=$(find "$MIGRATE_REMOVE_DIR" -name "*.sql" -size +0c 2>/dev/null | wc -l | tr -d ' ')
else
  REMOVE_COUNT=0
fi

[ "$ADD_COUNT" -gt 0 ] && HAS_MIGRATIONS="true"
[ "$REMOVE_COUNT" -gt 0 ] && HAS_REMOVE_MIGRATIONS="true"

echo "ACTIVE_ENV=$ACTIVE_ENV"
echo "TARGET_ENV=$TARGET_ENV"
echo "HAS_MIGRATIONS=$HAS_MIGRATIONS"
echo "HAS_REMOVE_MIGRATIONS=$HAS_REMOVE_MIGRATIONS"
