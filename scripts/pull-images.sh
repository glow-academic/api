#!/bin/bash
# Pull pre-built server image from GHCR and build database locally.
#
# Usage:
#   ./scripts/pull-images.sh [version]

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

VERSION="${1:-}"

if [ -n "$VERSION" ]; then
  echo "Pulling server image for version $VERSION..."
  docker pull "ghcr.io/learnloopllc/glow-api:$VERSION" || true
else
  echo "Pulling server image from compose..."
  docker compose pull server-blue server-green 2>/dev/null || true
fi

echo "Building database image locally..."
docker compose build database

echo "Image preparation complete"
