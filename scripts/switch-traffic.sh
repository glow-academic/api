#!/bin/bash
# Switch traffic to the specified environment.
#
# Usage:
#   ./scripts/switch-traffic.sh <blue|green>

set -e

TARGET_ENV="${1:?Usage: $0 <blue|green>}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

echo "Switching traffic to $TARGET_ENV..."

if grep -q "^ACTIVE_ENV=" .env 2>/dev/null; then
  sed -i.bak "s/^ACTIVE_ENV=.*/ACTIVE_ENV=$TARGET_ENV/" .env
  rm -f .env.bak
else
  echo "ACTIVE_ENV=$TARGET_ENV" >> .env
fi

docker compose up -d --no-deps nginx
sleep 5

echo "Traffic switched to $TARGET_ENV"
