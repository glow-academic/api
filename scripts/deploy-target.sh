#!/bin/bash
# Start target environment containers and wait for health checks.
#
# Usage:
#   ./scripts/deploy-target.sh <blue|green>
#   TIMEOUT=600 ./scripts/deploy-target.sh green

set -e

TARGET_ENV="${1:?Usage: $0 <blue|green>}"
TARGET_KC_ENV="${2:-$TARGET_ENV}"
MAX_WAIT="${TIMEOUT:-300}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

echo "Deploying $TARGET_ENV environment (keycloak: $TARGET_KC_ENV)..."

# Start infrastructure services first (database, redis, volume-init)
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

# Start keycloak and pgbouncer
echo "Starting keycloak-$TARGET_KC_ENV and pgbouncer..."
docker compose up -d "keycloak-$TARGET_KC_ENV" pgbouncer

# Restart ALL running keycloaks to refresh DB connections after database rebuild
for KC_COLOR in blue green; do
  if docker compose ps "keycloak-$KC_COLOR" --format '{{.Status}}' 2>/dev/null | grep -q "Up"; then
    echo "Restarting keycloak-$KC_COLOR (refresh DB connections)..."
    docker compose restart "keycloak-$KC_COLOR"
  fi
done

echo "Waiting for keycloak-$TARGET_KC_ENV to be healthy..."
ELAPSED=0
while [ $ELAPSED -lt 180 ]; do
  KC_HEALTHY=$(docker compose ps "keycloak-$TARGET_KC_ENV" --format json 2>/dev/null | jq -r '.Health // "unknown"' || echo "unknown")
  if [ "$KC_HEALTHY" = "healthy" ]; then
    echo "Keycloak ($TARGET_KC_ENV) is healthy"
    break
  fi
  echo "Waiting for keycloak-$TARGET_KC_ENV... (${ELAPSED}s/180s)"
  sleep 10
  ELAPSED=$((ELAPSED + 10))
done

if [ "$KC_HEALTHY" != "healthy" ]; then
  echo "Keycloak failed to become healthy, checking logs..."
  docker compose logs "keycloak-$TARGET_KC_ENV" --tail 20 2>/dev/null || true
  echo "Continuing anyway..."
fi

# Switch keycloak traffic before starting server (so server talks to the right keycloak)
echo "Switching keycloak traffic to $TARGET_KC_ENV..."
"${script_dir}/switch-kc-traffic.sh" "$TARGET_KC_ENV"

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
