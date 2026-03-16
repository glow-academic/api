#!/bin/bash
# Start target environment containers and wait for health checks.
#
# Usage:
#   ./scripts/deploy-target.sh <blue|green>
#   TIMEOUT=600 ./scripts/deploy-target.sh green

set -e

TARGET_ENV="${1:?Usage: $0 <blue|green>}"
MAX_WAIT="${TIMEOUT:-300}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

echo "Deploying $TARGET_ENV environment..."

# Start infrastructure services first (database, redis, keycloak, pgbouncer, volume-init)
echo "Starting infrastructure services..."
docker compose up -d volume-init database redis
sleep 5

echo "Waiting for database to be healthy..."
ELAPSED=0
while [ $ELAPSED -lt 120 ]; do
  DB_HEALTHY=$(docker compose ps database --format json 2>/dev/null | jq -r '.Health // "unknown"' || echo "unknown")
  if [ "$DB_HEALTHY" = "healthy" ]; then
    echo "Database is healthy"
    break
  fi
  sleep 5
  ELAPSED=$((ELAPSED + 5))
done

echo "Starting keycloak and pgbouncer..."
docker compose up -d keycloak pgbouncer

echo "Waiting for keycloak to be healthy..."
ELAPSED=0
while [ $ELAPSED -lt 180 ]; do
  KC_HEALTHY=$(docker compose ps keycloak --format json 2>/dev/null | jq -r '.Health // "unknown"' || echo "unknown")
  if [ "$KC_HEALTHY" = "healthy" ]; then
    echo "Keycloak is healthy"
    break
  fi
  echo "Waiting for keycloak... (${ELAPSED}s/180s)"
  sleep 10
  ELAPSED=$((ELAPSED + 10))
done

if [ "$KC_HEALTHY" != "healthy" ]; then
  echo "Keycloak failed to become healthy, checking logs..."
  docker compose logs keycloak --tail 20 2>/dev/null || true
  echo "Continuing anyway..."
fi

# Now start the server and docker-gen
echo "Starting server-$TARGET_ENV and docker-gen..."
docker compose up -d "server-$TARGET_ENV" docker-gen
sleep 5

# Wait for server to be healthy
echo "Waiting for $TARGET_ENV services to be healthy..."
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
  SERVER_HEALTHY=$(docker compose ps "server-$TARGET_ENV" --format json 2>/dev/null | jq -r '.Health // "unknown"' || echo "unknown")

  if [ "$SERVER_HEALTHY" = "healthy" ]; then
    echo "$TARGET_ENV environment is healthy"
    exit 0
  fi

  echo "Waiting for $TARGET_ENV to be healthy... (${ELAPSED}s/${MAX_WAIT}s)"
  sleep 10
  ELAPSED=$((ELAPSED + 10))
done

echo "$TARGET_ENV environment failed health checks after ${MAX_WAIT}s"
exit 1
