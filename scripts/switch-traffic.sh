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

# Update routing flags in .env (preserve other config)
if [ -f .env ]; then
  sed -i '/^ACTIVE_ENV=/d; /^ACTIVE_KC_ENV=/d' .env
fi
echo "ACTIVE_ENV=$TARGET_ENV" >> .env
echo "ACTIVE_KC_ENV=$CURRENT_KC_ENV" >> .env

docker compose up -d --no-deps nginx

# Move the `glow-api` Docker-network alias to the new active server.
# Clients (glow-client nginx, glow-docs) reach the backend via
# http://glow-api:8000 on the shared deployment network. Without this swap,
# both server-blue and server-green would carry the alias and Docker DNS
# would round-robin — splitting OIDC flows across active + inactive versions
# mid-login. provision.sh deliberately does NOT set this alias anymore.
PROJECT="${COMPOSE_PROJECT_NAME:-glow-api}"
DEPLOY_NETWORK="glow-${INSTANCE_ID:-$PROJECT}"
NEW_CONTAINER="${PROJECT}-server-${TARGET_ENV}-1"
OTHER_ENV=$([ "$TARGET_ENV" = "blue" ] && echo green || echo blue)
OTHER_CONTAINER="${PROJECT}-server-${OTHER_ENV}-1"

if docker network inspect "$DEPLOY_NETWORK" >/dev/null 2>&1; then
  echo "Reassigning glow-api alias on $DEPLOY_NETWORK → $NEW_CONTAINER"
  # Docker doesn't allow in-place alias edits; disconnect + reconnect.
  for c in "$NEW_CONTAINER" "$OTHER_CONTAINER"; do
    if docker inspect "$c" >/dev/null 2>&1; then
      docker network disconnect "$DEPLOY_NETWORK" "$c" 2>/dev/null || true
    fi
  done
  # Target gets the alias; the other rejoins the network without one.
  docker network connect --alias glow-api "$DEPLOY_NETWORK" "$NEW_CONTAINER"
  if docker inspect "$OTHER_CONTAINER" >/dev/null 2>&1; then
    docker network connect "$DEPLOY_NETWORK" "$OTHER_CONTAINER" 2>/dev/null || true
  fi
else
  echo "(deployment network $DEPLOY_NETWORK not found — skipping alias swap)"
fi

sleep 5

echo "Traffic switched to $TARGET_ENV"
