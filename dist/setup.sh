#!/bin/bash
# Glow — Self-hosted setup
#
# Usage:
#   1. Edit .env to set ORIGIN to your domain
#   2. Run: ./setup.sh
#   3. Access Glow at your ORIGIN URL

set -e

echo "=== Glow Self-Hosted Setup ==="

# Check .env exists
if [ ! -f .env ]; then
  echo "Error: .env file not found"
  echo "Copy .env.example to .env and configure it first"
  exit 1
fi

# Load images if they exist
if [ -d images ]; then
  echo "Loading Docker images..."
  for img in images/*.tar.gz; do
    [ -f "$img" ] || continue
    echo "  Loading $(basename $img)..."
    docker load < "$img"
  done
  echo "Images loaded"
fi

# Start everything
echo "Starting services..."
docker compose up -d

echo ""
echo "=== Setup complete ==="
echo "Glow is starting up. This may take a minute."
echo ""
echo "Check status: docker compose ps"
echo "View logs:    docker compose logs -f"
