#!/bin/bash
# Stage code to deployment directory via rsync.
#
# Usage:
#   ./scripts/stage-release.sh <source-dir> <dest-dir> [version]

set -e

SOURCE="${1:?Usage: $0 <source-dir> <dest-dir> [version]}"
DEST="${2:?Usage: $0 <source-dir> <dest-dir> [version]}"
VERSION="${3:-}"

mkdir -p "$DEST"

rsync -a --delete \
  --exclude='.git/' \
  --exclude='.github/' \
  --exclude='.venv/' \
  --exclude='docker-compose.override.yml' \
  --exclude='.env' \
  --exclude='.docker/' \
  --exclude='glow-deploy.local.yaml' \
  "$SOURCE/" "$DEST/"

if [ -n "$VERSION" ]; then
  echo "$VERSION" > "$DEST/DEPLOYED_VERSION"
fi

# Ensure history dir is writable by LearnLoop API container (uid 1001)
# for backup creation via the bind mount at /app/glow-deployments/{id}/history/
mkdir -p "$DEST/history"
chmod 777 "$DEST/history"

echo "Release staged to $DEST"
