.PHONY: help setup install clean format lint typecheck run test test-cov cleanup generate-tests stop restore-db connect-db migrate openapi-gen configure deploy deploy-clean seed-gen sync-types
.PHONY: deploy-target switch-traffic switch-kc-traffic rollback monitor deploy-status detect-env pull-images stage-release

# Default Python interpreter
PYTHON := python3.11
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip

# Service ports
SERVER_PORT := 8000
REDIS_PORT := 6380
DATABASE_PORT := 5432
KEYCLOAK_PORT := 8080

# Check if Python 3.11 is available
PY311 := $(shell which python3.11 || true)

# Arguments for test command
ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

# Check if Python 3.11 is available
check-python:
	@if [ -z "$(PY311)" ]; then \
		echo "❌  python3.11 not found - please install Python 3.11"; \
		exit 1; \
	fi

# Setup: copy .env.example to .env if missing (optional for local dev; docker compose has defaults)
setup:
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example — edit for production"; else echo ".env already exists"; fi

# Create virtual environment
setup-venv: check-python
	@echo "Creating virtual environment at $(VENV)..."
	@$(PYTHON) -m venv $(VENV)
	@echo "✅ Virtual environment created at $(VENV)"
	@echo "To activate: source $(VENV_BIN)/activate"

# Alias for setup
configure: setup

# Deploy: start services (uses templates from history/)
deploy:
	@echo "🚀 Deploying Glow..."
	@docker compose up -d --build
	@echo "✅ Deploy complete"

# Deploy clean: wipe volumes, start fresh
deploy-clean:
	@echo "🚀 Deploying Glow (clean)..."
	@docker compose down -v
	@docker compose up -d --build
	@echo "✅ Clean deploy complete"

# Install all dependencies
install: check-venv
	@echo "Installing all dependencies..."
	@$(VENV_PIP) install --upgrade pip
	@$(VENV_PIP) install -e .
	@if [ -f database/package.json ] && [ ! -d database/node_modules ]; then \
		echo "Installing database dependencies..."; \
		cd database && yarn install; \
	fi
	@echo "✅ All dependencies installed"

# Clean virtual environment
clean:
	@echo "Removing virtual environment..."
	@rm -rf $(VENV)
	@echo "✅ Virtual environment removed"

# Check if virtual environment exists
check-venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "❌ Virtual environment not found at $(VENV)"; \
		echo "Run 'make setup' to create it"; \
		exit 1; \
	fi
	@if [ ! -f "$(VENV_PYTHON)" ]; then \
		echo "❌ Python not found in virtual environment at $(VENV_PYTHON)"; \
		echo "Run 'make setup' to recreate the virtual environment"; \
		exit 1; \
	fi

# Format code with Ruff
format: check-venv
	@echo "Formatting code with Ruff..."
	@$(VENV_PYTHON) -m ruff format .
	@$(VENV_PYTHON) -m ruff check --fix .
	@echo "✅ Code formatted"

# Run linter checks
lint: check-venv
	@echo "Running linter..."
	@$(VENV_PYTHON) -m ruff check .
	@echo "✅ Linting complete"

# Run MyPy for static type checking
typecheck: check-venv
	@echo "Type checking..."
	@$(VENV_PYTHON) -m mypy core/app core/utils
	@echo "✅ Type checking complete"


# Generate pytest tests for routes and services
generate-tests: check-venv
	@echo "Generating pytest tests..."
	@$(VENV_PYTHON) core/scripts/generate_pytest_tests.py
	@echo "✅ Tests generated"


# Run all tests
test: check-venv
	@if [ -n "$(ARGS)" ]; then \
		echo "Running tests: $(ARGS)"; \
		$(VENV_PYTHON) -m pytest $(ARGS) -v; \
	else \
		echo "Running tests..."; \
		$(VENV_PYTHON) -m pytest core/tests/ -v; \
	fi

# Run tests with coverage
test-cov: check-venv
	@if [ -n "$(ARGS)" ]; then \
		echo "Running tests with coverage: $(ARGS)"; \
		COVERAGE_FILE=core/.coverage $(VENV_PYTHON) -m pytest $(ARGS) --cov=core/app --cov-report=term-missing --cov-report=html:core/htmlcov; \
	else \
		echo "Running tests with coverage..."; \
		COVERAGE_FILE=core/.coverage $(VENV_PYTHON) -m pytest core/tests/ --cov=core/app --cov-report=term-missing --cov-report=html:core/htmlcov; \
	fi
	@echo "✅ Coverage report generated at core/htmlcov/index.html"

# Generate OpenAPI schema manually
openapi-gen: check-venv
	@echo "📝 Generating OpenAPI schema..."
	@cd core && $(PWD)/$(VENV_PYTHON) -c "import json; \
from fastapi.openapi.utils import get_openapi; \
from app.main import fastapi_app; \
import pathlib; \
	p = pathlib.Path.cwd().parent / 'openapi.json'; \
p.write_text(json.dumps(get_openapi(title=fastapi_app.title, version='0.1.0', routes=fastapi_app.routes, description='Auto-generated OpenAPI schema'), indent=2)); \
print('✅ openapi.json written to', p.resolve())"

# Provision a deployment token from the LearnLoop API (local dev only).
# Creates a fresh provision token in the learnloop DB, claims it via HTTP,
# and exports DEPLOYMENT_TOKEN for the server process.
# Requires: learnloop-api running on AUTH_ISSUER (default http://localhost:8100).
provision-token:
	@LEARNLOOP_DB=$${LEARNLOOP_DB_NAME:-learnloopapi}; \
	LEARNLOOP_URL=$${AUTH_ISSUER:-http://localhost:8100}; \
	DB_U=$${DB_USER:-myuser}; \
	DB_P=$${DB_PASSWORD:-mypassword}; \
	DB_H=$${DB_HOST:-localhost}; \
	DB_PT=$${DB_PORT:-5432}; \
	TOKEN=$$(PGPASSWORD=$$DB_P psql -h $$DB_H -p $$DB_PT -U $$DB_U -d $$LEARNLOOP_DB -tAqc " \
		INSERT INTO provision_tokens (organization_id, deployment_id, token, expires_at) \
		SELECT d.organization_id, d.id, 'pt_' || encode(gen_random_bytes(32), 'hex'), \
		       NOW() + interval '1 hour' \
		FROM deployments d WHERE d.name = 'glow-api' AND d.active = true \
		RETURNING token" 2>/dev/null | head -1 | tr -d '[:space:]'); \
	if [ -z "$$TOKEN" ]; then \
		echo "⚠️  Could not create provision token (is learnloop DB seeded?)"; \
		echo "   Continuing without DEPLOYMENT_TOKEN..."; \
	else \
		DT=$$(printf '{"token":"%s"}' "$$TOKEN" | curl -sf -X POST "$$LEARNLOOP_URL/provision/claim" \
			-H 'Content-Type: application/json' \
			-d @- | $(VENV_PYTHON) -c "import sys,json; print(json.load(sys.stdin).get('deployment_token',''))" 2>/dev/null); \
		if [ -n "$$DT" ]; then \
			echo "$$DT"; \
		else \
			echo "⚠️  Could not claim provision token (is learnloop-api running on $$LEARNLOOP_URL?)"; \
		fi; \
	fi

# Start all services in foreground with combined logs
run: check-venv
	@echo "🚀 Starting GLOW API services..."
	@echo "  Redis:    localhost:$(REDIS_PORT)"
	@echo "  Server:   http://localhost:$(SERVER_PORT)"
	@echo "  Database: localhost:$(DATABASE_PORT)"
	@echo "  Keycloak: http://localhost:$(KEYCLOAK_PORT)"
	@echo ""
	@echo "Press Ctrl+C to stop all services"
	@echo "----------------------------------------"
	@psql postgresql://$${DB_USER:-myuser}:$${DB_PASSWORD:-mypassword}@localhost:$(DATABASE_PORT)/$${DB_NAME:-glowapi} -c "CREATE SCHEMA IF NOT EXISTS keycloak; CREATE SCHEMA IF NOT EXISTS migrations;" 2>/dev/null || true
	@DEPLOYMENT_TOKEN=$$($(MAKE) -s provision-token 2>/dev/null); \
	if [ -n "$$DEPLOYMENT_TOKEN" ]; then \
		echo "✅ Deployment token provisioned"; \
	else \
		echo "⚠️  No deployment token (learnloop-api not running?)"; \
	fi; \
	export DEPLOYMENT_TOKEN; \
	trap 'echo ""; echo "🛑 Stopping all services..."; pkill -f "redis-server.*$(REDIS_PORT)" 2>/dev/null || true; pkill -f "uvicorn.*$(SERVER_PORT)" 2>/dev/null || true; pkill -f "stream-logs.js" 2>/dev/null || true; pkill -f "docker logs.*glow-keycloak" 2>/dev/null || true; echo "✅ All services stopped (run make stop to also stop Keycloak)"; exit 0' INT; \
	exec 2>/dev/null; \
	if docker ps --filter name=glow-keycloak --format "{{.Names}}" | grep -q "^glow-keycloak$$"; then \
		echo "✅ Keycloak already running, attaching to logs..."; \
		(docker logs --tail 0 -f glow-keycloak 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;34m[KEYCLOAK]\033[0m %s' "$$line")"; done) & \
	elif docker ps -a --filter name=glow-keycloak --format "{{.Names}}" | grep -q "^glow-keycloak$$"; then \
		echo "🔄 Starting existing Keycloak container..."; \
		docker start glow-keycloak >/dev/null 2>&1; \
		sleep 1; \
		(docker logs --tail 0 -f glow-keycloak 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;34m[KEYCLOAK]\033[0m %s' "$$line")"; done) & \
	else \
		echo "🚀 Creating new Keycloak container..."; \
		DB_USER=$${DB_USER:-myuser}; \
		DB_PASSWORD=$${DB_PASSWORD:-mypassword}; \
		APP_PREFIX=$${APP_PREFIX:-}; \
		docker run -d --name glow-keycloak -p $(KEYCLOAK_PORT):8080 \
			-v "$(PWD)/uploads/themes:/opt/keycloak/themes:ro" \
			-e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
			-e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
			-e KC_DB=postgres \
			-e KC_DB_URL=jdbc:postgresql://host.docker.internal:5432/$${DB_NAME:-glowapi}?currentSchema=keycloak \
			-e KC_DB_USERNAME=$$DB_USER \
			-e KC_DB_PASSWORD=$$DB_PASSWORD \
		-e KC_DB_SCHEMA=keycloak \
		-e KC_PROXY=none \
		-e KC_HTTP_ENABLED=true \
		-e KC_HTTP_RELATIVE_PATH=/auth \
		-e KC_HOSTNAME=http://localhost:$(KEYCLOAK_PORT)/auth \
		-e KC_HOSTNAME_STRICT=false \
		-e KC_HOSTNAME_STRICT_BACKCHANNEL=false \
		-e KC_HOSTNAME_STRICT_HTTPS=false \
		-e KC_SPI_STICKY_SESSION_ENCODER_INFINISPAN_SHOULD_ATTACH_ROUTE=false \
			quay.io/keycloak/keycloak:26.0 start-dev >/dev/null 2>&1; \
		sleep 1; \
		(docker logs --tail 0 -f glow-keycloak 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;34m[KEYCLOAK]\033[0m %s' "$$line")"; done) & \
	fi; \
	echo "⏳ Waiting for Keycloak to be ready..."; \
	for i in $$(seq 1 60); do \
		if docker exec glow-keycloak /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080/auth --realm master --user admin --password admin 2>/dev/null; then \
			echo "✅ Keycloak is ready"; \
			docker exec glow-keycloak /opt/keycloak/bin/kcadm.sh update realms/master -s sslRequired=NONE 2>/dev/null && echo "✅ Keycloak SSL requirement disabled" || echo "⚠️  Keycloak SSL already configured"; \
			break; \
		fi; \
		sleep 2; \
	done; \
	(cd core && redis-server --port $(REDIS_PORT) --dir . --dbfilename dump.rdb 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;31m[REDIS]\033[0m %s' "$$line")"; done) & \
	(cd core && ( $(PWD)/$(VENV_PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port $(SERVER_PORT) --reload-exclude '**/openapi.json' --reload-exclude 'app/sql/types.py' --reload-exclude 'tests/sql/types.py') 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;32m[SERVER]\033[0m %s' "$$line")"; done) & \
	(cd database && READS=1 MIN_MS=0 SAMPLE_MS=150 DEBUG_READS=1 yarn logs 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;33m[DATABASE]\033[0m %s' "$$line")"; done) & \
	wait

# Stop all services (for cleanup)
stop:
	@echo "🛑 Stopping all GLOW services..."
	@echo "Stopping Redis..."
	@pkill -f "redis-server.*$(REDIS_PORT)" 2>/dev/null && echo "✅ Redis stopped" || echo "⚠️  Redis not running"
	@echo "Stopping Server..."
	@pkill -f "uvicorn.*$(SERVER_PORT)" 2>/dev/null && echo "✅ Server stopped" || echo "⚠️  Server not running"
	@echo "Stopping Database logs..."
	@pkill -f "stream-logs.js" 2>/dev/null && echo "✅ Database logs stopped" || echo "⚠️  Database logs not running"
	@echo "Stopping Keycloak..."
	@if docker ps -a --filter name=glow-keycloak --format "{{.Names}}" | grep -q "^glow-keycloak$$"; then \
		docker stop glow-keycloak >/dev/null 2>&1 && echo "✅ Keycloak stopped" || echo "⚠️  Failed to stop Keycloak"; \
		docker rm glow-keycloak >/dev/null 2>&1 && echo "✅ Keycloak container removed" || echo "⚠️  Failed to remove Keycloak container"; \
	else \
		echo "⚠️  Keycloak container not found"; \
	fi
	@echo "✅ All services stopped"

# Clean up generated files and cache
cleanup:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.pyd" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf core/.pytest_cache core/.mypy_cache core/.ruff_cache 2>/dev/null || true
	@rm -rf core/htmlcov core/.coverage 2>/dev/null || true
	@rm -f core/dump.rdb 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Restore database from a backup (default: fresh.sql.gz, override via DB_BACKUP env or arg)
# Usage: make restore-db  OR  make restore-db DB_BACKUP=university.sql.gz
DB_BACKUP ?= fresh.sql.gz
restore-db:
	@DB_BACKUP=$(DB_BACKUP) bash database/scripts/start.sh
	@rm -rf uploads/ledger && mkdir -p uploads/ledger && echo "✅ Ledger cleared"
	@python3 -c "import json,hashlib,hmac,os;from datetime import datetime,timezone;from pathlib import Path;s=os.getenv('SECRET_KEY','dev-secret-key');e={'sequence':0,'previous_hash':'0'*64,'timestamp':datetime.now(timezone.utc).isoformat(),'attempt_id':None,'profile_id':None,'is_checkpoint':True,'checkpoint':{'authorized':True,'num_left':None,'num_to_next_check':9999,'message':'Dev bypass','meta':{}},'num_left':None,'num_to_next_check':9999,'hash':''};p={k:v for k,v in e.items() if k!='hash'};e['hash']=hmac.new(s.encode(),json.dumps(p,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest();Path('uploads/ledger/000000.json').write_text(json.dumps(e,indent=2));print('✅ Ledger bypass entry created (num_to_next_check=9999)')"

# Migrate: restore fresh, apply all migrations, update schema, regenerate templates
migrate: check-venv
	@echo "Restoring from fresh template..."
	@DB_BACKUP=fresh.sql.gz bash database/scripts/start.sh
	@echo ""
	@echo "Applying additive migrations..."
	@export PGPASSWORD="$${DB_PASSWORD:-mypassword}"; \
	for f in $$(ls database/migrate/add/*.sql 2>/dev/null | sort); do \
		echo "  Applying (add): $$(basename $$f)"; \
		psql -h "$${DB_HOST:-localhost}" -p "$${DB_PORT:-5432}" -U "$${DB_USER:-myuser}" -d "$${DB_NAME:-glowapi}" -v ON_ERROR_STOP=1 -f "$$f" > /dev/null; \
	done
	@echo "Applying destructive migrations..."
	@export PGPASSWORD="$${DB_PASSWORD:-mypassword}"; \
	for f in $$(ls database/migrate/remove/*.sql 2>/dev/null | sort); do \
		case "$$f" in *.gitkeep) continue;; esac; \
		echo "  Applying (remove): $$(basename $$f)"; \
		psql -h "$${DB_HOST:-localhost}" -p "$${DB_PORT:-5432}" -U "$${DB_USER:-myuser}" -d "$${DB_NAME:-glowapi}" -v ON_ERROR_STOP=1 -f "$$f" > /dev/null; \
	done
	@echo "Updating schema.sql..."
	@pg_dump --schema-only --no-owner --no-privileges --exclude-schema=keycloak --format=plain \
		--file=database/schema.sql \
		"postgresql://$${DB_USER:-myuser}:$${DB_PASSWORD:-mypassword}@$${DB_HOST:-localhost}:$${DB_PORT:-5432}/$${DB_NAME:-glowapi}"
	@$(MAKE) split-schema
	@echo ""
	@echo "Regenerating templates..."
	@$(MAKE) seed-gen
	@echo ""
	@echo "Migration complete. Templates updated in history/"

# Split schema.sql into structured files
split-schema:
	@echo "Splitting schema.sql into structured files..."
	@python3 database/scripts/split_schema.py
	@echo "✅ Schema split complete"

# Concatenate split schema files back into schema.sql
concat-schema:
	@echo "Concatenating schema files..."
	@bash database/scripts/concat_schema.sh
	@echo "✅ Schema concatenated"


# Generate registry files from DB introspection + filesystem scanning
registry: check-venv
	@echo "Generating registry files..."
	@PYTHONPATH=core DB_USER="$${DB_USER:-myuser}" \
	 DB_PASSWORD="$${DB_PASSWORD:-mypassword}" \
	 DB_NAME="$${DB_NAME:-glowapi}" \
	 DB_HOST="$${DB_HOST:-localhost}" \
	 DB_PORT="$${DB_PORT:-5432}" \
	 $(VENV_PYTHON) core/scripts/generate_registry.py all
	@echo "✅ Registry generation complete"

# Validate registry files match DB state
registry-validate: check-venv
	@echo "Validating registry files..."
	@PYTHONPATH=core DB_USER="$${DB_USER:-myuser}" \
	 DB_PASSWORD="$${DB_PASSWORD:-mypassword}" \
	 DB_NAME="$${DB_NAME:-glowapi}" \
	 DB_HOST="$${DB_HOST:-localhost}" \
	 DB_PORT="$${DB_PORT:-5432}" \
	 $(VENV_PYTHON) core/scripts/generate_registry.py validate
	@echo "✅ Registry validation complete"


# Connect to database
connect-db:
	@psql -h "$${DB_HOST:-localhost}" -p "$${DB_PORT:-5432}" -U "$${DB_USER:-myuser}" -d "$${DB_NAME:-glowapi}"

# Regenerate all template backups in history/ via testcontainers
seed-gen: check-venv
	@echo "Regenerating all templates..."
	@PYTHONPATH=core $(VENV_PYTHON) -m database.scripts.runner --all


# MCP setup for Cursor IDE
mcp: check-venv
	@echo "Setting up MCP for Cursor IDE..."
	@echo "1. Configuring Keycloak token lifespan..."
	@$(VENV_PYTHON) core/scripts/configure-mcp-token-lifespan.py || echo "⚠️  Could not configure token lifespan (Keycloak may not be running)"
	@echo "2. Getting token and updating Cursor config..."
	@$(VENV_PYTHON) scripts/setup-cursor-mcp.py
	@echo ""
	@echo "✅ MCP setup complete!"
	@echo "   - Token lifetime: $(shell $(VENV_PYTHON) -c 'import os; from dotenv import load_dotenv; load_dotenv(); print(f\"{int(os.getenv(\"MCP_TOKEN_LIFESPAN\", \"86400\")) // 3600} hours\")' 2>/dev/null || echo '24 hours') (configurable via MCP_TOKEN_LIFESPAN)"
	@echo "   - Cursor config updated at ~/.cursor/mcp.json"
	@echo "   - Restart Cursor IDE to use the new configuration"


# ── Docker (production-like stack) ───────────────────────────
.PHONY: up down docker-logs

up:
	docker compose up -d
	@echo "Full stack running"

down:
	docker compose down

docker-logs:
	docker compose logs -f

# ── Deployment ───────────────────────────────────────────────
deploy-target:
	./scripts/deploy-target.sh $(ENV)

switch-traffic:
	./scripts/switch-traffic.sh $(ENV)

switch-kc-traffic:
	./scripts/switch-kc-traffic.sh $(KC_ENV)

rollback:
	./scripts/switch-traffic.sh $(ROLLBACK_ENV)

monitor:
	./scripts/monitor.sh $(ENV) $(ROLLBACK_ENV) $(GRACE)

detect-env:
	./scripts/detect-env.sh

pull-images:
	./scripts/pull-images.sh

stage-release:
	./scripts/stage-release.sh . $(DEST) $(SHA)

migrate-docker:
	./scripts/migrate-docker.sh $(TYPE)

# Sync upstream API version for compat tracking
LEARNLOOP_API_URL ?= http://localhost:8100
sync-types: ## Record LearnLoop API version this glow-api integrates with
	@echo "Fetching LearnLoop API version from $(LEARNLOOP_API_URL)..."
	@curl -sf $(LEARNLOOP_API_URL)/openapi.json -o /tmp/ll-openapi.json
	@echo "{\"learnloop-api\":{\"version\":\"$$(jq -r '.info.version' /tmp/ll-openapi.json)\",\"synced_at\":\"$$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}" | jq . > api-versions.json
	@rm -f /tmp/ll-openapi.json
	@echo "✅ api-versions.json updated"

# Show help
help:
	@echo "GLOW - Graduate Learning Orientation Workshop"
	@echo ""
	@echo "Getting started:"
	@echo "  setup          - Copy .env.example to .env"
	@echo "  deploy         - Start all Docker services"
	@echo "  deploy-clean   - Wipe volumes and start fresh"
	@echo ""
	@echo "Environment setup:"
	@echo "  setup-venv   - Create virtual environment at .venv"
	@echo "  install      - Install all dependencies in venv"
	@echo "  clean        - Remove virtual environment"
	@echo ""
	@echo "Database:"
	@echo "  restore-db [DB_BACKUP=x] - Restore DB from backup (default: fresh.sql.gz)"
	@echo "  connect-db               - Connect to database via psql"
	@echo "  seed-gen                 - Regenerate all templates in history/"
	@echo "  migrate                  - Apply migrations + update schema + regenerate templates"
	@echo ""
	@echo "Docker (production-like):"
	@echo "  up             - Start full docker compose stack"
	@echo "  down           - Stop docker compose stack"
	@echo "  docker-logs    - Tail docker compose logs"
	@echo ""
	@echo "Services:"
	@echo "  run          - Start all services in foreground (Ctrl+C to stop)"
	@echo "  stop         - Stop all services including Keycloak"
	@echo ""
	@echo "Code quality:"
	@echo "  format       - Format code with Ruff"
	@echo "  lint         - Run linter checks"
	@echo "  typecheck    - Run MyPy for static type checking"
	@echo "Testing:"
	@echo "  test         - Run server unit tests (pytest)"
	@echo "  test-cov     - Run server tests with coverage"
	@echo ""
	@echo "Utilities:"
	@echo "  cleanup      - Clean up generated files and cache"
	@echo "  mcp          - Setup MCP for Cursor IDE"
	@echo ""
	@echo "Service URLs:"
	@echo "  Redis:     localhost:$(REDIS_PORT)"
	@echo "  Server:    http://localhost:$(SERVER_PORT)"
	@echo "  Database:  localhost:$(DATABASE_PORT)"
	@echo "  Keycloak:  http://localhost:$(KEYCLOAK_PORT)"
