#!/bin/bash
# Switch keycloak traffic to the specified environment.
#
# Preserves the current ACTIVE_ENV (server routing) and only changes ACTIVE_KC_ENV.
#
# Usage:
#   ./scripts/switch-kc-traffic.sh <blue|green>

set -e

TARGET_KC_ENV="${1:?Usage: $0 <blue|green>}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

# Preserve current server routing
NGINX_CONTAINER="${COMPOSE_PROJECT_NAME:-glow-api}-nginx"
CURRENT_ACTIVE_ENV=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$NGINX_CONTAINER" 2>/dev/null | grep '^ACTIVE_ENV=' | cut -d= -f2 || echo "blue")
CURRENT_ACTIVE_ENV="${CURRENT_ACTIVE_ENV:-blue}"

echo "Switching keycloak traffic to $TARGET_KC_ENV (server stays $CURRENT_ACTIVE_ENV)..."

export ACTIVE_ENV="$CURRENT_ACTIVE_ENV"
export ACTIVE_KC_ENV="$TARGET_KC_ENV"

# Update routing flags in .env (preserve other config)
if [ -f .env ]; then
  sed -i '/^ACTIVE_ENV=/d; /^ACTIVE_KC_ENV=/d' .env
fi
echo "ACTIVE_ENV=$CURRENT_ACTIVE_ENV" >> .env
echo "ACTIVE_KC_ENV=$TARGET_KC_ENV" >> .env

docker compose up -d --no-deps nginx

sleep 5

echo "Keycloak traffic switched to $TARGET_KC_ENV"
