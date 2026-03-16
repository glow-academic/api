#!/bin/bash
# Main deployment CLI — single entry point for all deploy operations.
#
# Usage:
#   ./scripts/deploy.sh                  # Full blue-green deploy (auto-detect target)
#   ./scripts/deploy.sh deploy [env]     # Deploy to specific env
#   ./scripts/deploy.sh switch <env>     # Switch traffic to env
#   ./scripts/deploy.sh rollback         # Switch back to previous env
#   ./scripts/deploy.sh status           # Show current status
#   ./scripts/deploy.sh migrate <type>   # Run migrations in Docker (add|remove|all)
#   ./scripts/deploy.sh scale <env> [n]  # Scale environment to N instances

set -e

COMMAND="${1:-deploy}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

# Load .env if it exists
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

case "$COMMAND" in
  deploy)
    ENV="${2:-}"
    if [ -z "$ENV" ]; then
      eval $(./scripts/detect-env.sh)
      ENV="$TARGET_ENV"
    fi
    echo "Deploying to $ENV..."
    ./scripts/pull-images.sh
    ./scripts/deploy-target.sh "$ENV"
    ./scripts/switch-traffic.sh "$ENV"
    ./scripts/monitor.sh "$ENV"
    ;;

  switch)
    ENV="${2:?Usage: $0 switch <blue|green>}"
    ./scripts/switch-traffic.sh "$ENV"
    ;;

  rollback)
    # Detect current active, switch to the other
    eval $(./scripts/detect-env.sh)
    echo "Rolling back: switching traffic from $ACTIVE_ENV to $TARGET_ENV..."
    ./scripts/switch-traffic.sh "$TARGET_ENV"
    ;;

  status)
    eval $(./scripts/detect-env.sh)
    echo "Active environment: $ACTIVE_ENV"
    echo "Target environment: $TARGET_ENV"
    echo "Has pending migrations: $HAS_MIGRATIONS"
    echo "Has remove migrations: $HAS_REMOVE_MIGRATIONS"
    echo ""
    docker compose ps
    ;;

  migrate)
    TYPE="${2:-all}"
    ./scripts/migrate-docker.sh "$TYPE"
    ;;

  scale)
    ENV="${2:?Usage: $0 scale <blue|green> [instances]}"
    INSTANCES="${3:-3}"
    echo "Scaling $ENV to $INSTANCES instances..."
    docker compose up -d --scale "server-$ENV=$INSTANCES"
    echo "$ENV scaled to $INSTANCES instances"
    ;;

  help|*)
    echo "GLOW API Deployment CLI"
    echo ""
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  deploy [env]        Full blue-green deploy (auto-detect target, or specify env)"
    echo "  switch <env>        Switch traffic to blue or green"
    echo "  rollback            Switch traffic back to previous environment"
    echo "  status              Show active/target env, migration status, container health"
    echo "  migrate <type>      Run migrations in Docker (add|remove|all)"
    echo "  scale <env> [n]     Scale environment to N instances (default: 3)"
    echo "  help                Show this help"
    [ "$COMMAND" != "help" ] && exit 1
    ;;
esac
