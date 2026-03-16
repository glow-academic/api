#!/bin/bash
# Pull pre-built images from GHCR.
#
# Usage:
#   ./scripts/pull-images.sh [version]

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

VERSION="${1:-}"

if [ -n "$VERSION" ]; then
  echo "Pulling images for version $VERSION..."
  docker pull "ghcr.io/learnloopllc/glow-api-server:$VERSION" || true
  docker pull "ghcr.io/learnloopllc/glow-api-database:$VERSION" || true
else
  echo "Pulling images from compose..."
  docker compose pull server-blue server-green database 2>/dev/null || true
fi

echo "Image pull complete"
