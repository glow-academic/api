#!/bin/bash
# Switch server traffic to the specified environment.
#
# Preserves the current ACTIVE_KC_ENV (keycloak routing) and only changes ACTIVE_ENV.
#
# Usage:
#   ./scripts/switch-traffic.sh <blue|green>

set -e

TARGET_ENV="${1:?Usage: $0 <blue|green>}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

# Preserve current keycloak routing
NGINX_CONTAINER="${COMPOSE_PROJECT_NAME:-glow-api}-nginx"
CURRENT_KC_ENV=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$NGINX_CONTAINER" 2>/dev/null | grep '^ACTIVE_KC_ENV=' | cut -d= -f2 || echo "blue")
CURRENT_KC_ENV="${CURRENT_KC_ENV:-blue}"

echo "Switching server traffic to $TARGET_ENV (keycloak stays $CURRENT_KC_ENV)..."

export ACTIVE_ENV="$TARGET_ENV"
export ACTIVE_KC_ENV="$CURRENT_KC_ENV"

# Persist routing so restarts pick it up
echo "ACTIVE_ENV=$TARGET_ENV" > .env
echo "ACTIVE_KC_ENV=$CURRENT_KC_ENV" >> .env

docker compose up -d --no-deps nginx

sleep 5

echo "Traffic switched to $TARGET_ENV"
