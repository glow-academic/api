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
  --exclude='.env' \
  --exclude='docker-compose.override.yml' \
  "$SOURCE/" "$DEST/"

if [ -n "$VERSION" ]; then
  echo "$VERSION" > "$DEST/DEPLOYED_VERSION"
fi

echo "Release staged to $DEST"
