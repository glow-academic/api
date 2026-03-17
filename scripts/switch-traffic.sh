#!/bin/bash
# Switch traffic to the specified environment.
#
# Sets ACTIVE_ENV and recreates nginx to apply the new routing.
# No .env file needed — ACTIVE_ENV is passed via environment.
#
# Usage:
#   ./scripts/switch-traffic.sh <blue|green>

set -e

TARGET_ENV="${1:?Usage: $0 <blue|green>}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

echo "Switching traffic to $TARGET_ENV..."

# Export ACTIVE_ENV so docker compose picks it up for nginx
export ACTIVE_ENV="$TARGET_ENV"

# Recreate nginx to apply new config
docker compose up -d --no-deps nginx

# Wait for nginx to be ready
sleep 5

echo "Traffic switched to $TARGET_ENV"
