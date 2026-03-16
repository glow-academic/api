.PHONY: help setup install clean format lint typecheck run test test-cov cleanup generate-tests stop install-client restore-db migrate-db migrate-db-only migrate-db-all connect-db fresh-db typecheck-client build-client openapi-gen gen-client-types configure deploy deploy-clean seed-gen

# Default Python interpreter
PYTHON := python3.11
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip

# Service ports
SERVER_PORT := 8000
CLIENT_PORT := 3000
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

# Setup: copy .env.example to .env
setup:
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example — edit it with your values"; else echo ".env already exists"; fi

# Create virtual environment
setup-venv: check-python
	@echo "Creating virtual environment at $(VENV)..."
	@$(PYTHON) -m venv $(VENV)
	@echo "✅ Virtual environment created at $(VENV)"
	@echo "To activate: source $(VENV_BIN)/activate"

# Alias for setup
configure: setup

# Deploy: build seed SQL, start services
deploy:
	@echo "🚀 Deploying Glow..."
	@bash database/scripts/load-modules.sh --output database/seeds/seed_modules.sql
	@docker compose up -d --build
	@echo "✅ Deploy complete"

# Deploy clean: wipe volumes, build seed SQL, start fresh
deploy-clean:
	@echo "🚀 Deploying Glow (clean)..."
	@bash database/scripts/load-modules.sh --output database/seeds/seed_modules.sql
	@docker compose down -v
	@docker compose up -d --build
	@echo "✅ Clean deploy complete"

# Install all dependencies
install: check-venv
	@echo "Installing all dependencies..."
	@$(VENV_PIP) install --upgrade pip
	@$(VENV_PIP) install -e .
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
	@$(VENV_PYTHON) -m mypy server/app server/utils
	@echo "✅ Type checking complete"


# Generate pytest tests for routes and services
generate-tests: check-venv
	@echo "Generating pytest tests..."
	@$(VENV_PYTHON) server/scripts/generate_pytest_tests.py
	@echo "✅ Tests generated"


# Run all tests
test: check-venv
	@if [ -n "$(ARGS)" ]; then \
		echo "Running tests: $(ARGS)"; \
		$(VENV_PYTHON) -m pytest $(ARGS) -v; \
	else \
		echo "Running tests..."; \
		$(VENV_PYTHON) -m pytest server/tests/ -v; \
	fi

# Run tests with coverage
test-cov: check-venv
	@if [ -n "$(ARGS)" ]; then \
		echo "Running tests with coverage: $(ARGS)"; \
		COVERAGE_FILE=server/.coverage $(VENV_PYTHON) -m pytest $(ARGS) --cov=server/app --cov-report=term-missing --cov-report=html:server/htmlcov; \
	else \
		echo "Running tests with coverage..."; \
		COVERAGE_FILE=server/.coverage $(VENV_PYTHON) -m pytest server/tests/ --cov=server/app --cov-report=term-missing --cov-report=html:server/htmlcov; \
	fi
	@echo "✅ Coverage report generated at server/htmlcov/index.html"

# Run client typecheck
typecheck-client:
	@echo "Running client typecheck..."
	@cd client && yarn typecheck
	@echo "✅ Client typecheck complete"

# Build client for production
build-client:
	@echo "Building client for production..."
	@cd client && yarn build
	@echo "✅ Client build complete"

# Generate OpenAPI schema manually
openapi-gen: check-venv
	@echo "📝 Generating OpenAPI schema..."
	@cd server && $(PWD)/$(VENV_PYTHON) -c "import json; \
from fastapi.openapi.utils import get_openapi; \
from app.main import fastapi_app; \
import pathlib; \
p = pathlib.Path('openapi.json'); \
p.write_text(json.dumps(get_openapi(title=fastapi_app.title, version='0.1.0', routes=fastapi_app.routes, description='Auto-generated OpenAPI schema'), indent=2)); \
print('✅ openapi.json written to', p.resolve())"

# Generate client TypeScript types from OpenAPI
gen-client-types:
	@echo "📝 Generating client TypeScript types from OpenAPI..."
	@cd client && yarn gen:types
	@echo "✅ Client types updated in lib/api/schema.ts"


# Start all services in foreground with combined logs
run: check-venv
	@echo "🚀 Starting all GLOW services..."
	@echo "  Redis:    localhost:$(REDIS_PORT)"
	@echo "  Server:   http://localhost:$(SERVER_PORT)"
	@echo "  Client:   http://localhost:$(CLIENT_PORT)"
	@echo "  Database: localhost:$(DATABASE_PORT)"
	@echo "  Keycloak: http://localhost:$(KEYCLOAK_PORT)"
	@echo ""
	@echo "Press Ctrl+C to stop all services"
	@echo "----------------------------------------"
	@trap 'echo ""; echo "🛑 Stopping all services..."; pkill -f "redis-server.*$(REDIS_PORT)" 2>/dev/null || true; pkill -f "uvicorn.*$(SERVER_PORT)" 2>/dev/null || true; pkill -f "next dev" 2>/dev/null || true; pkill -f "chokidar.*openapi.json" 2>/dev/null || true; pkill -f "chokidar.*sql" 2>/dev/null || true; pkill -f "stream-logs.js" 2>/dev/null || true; pkill -f "docker logs.*glow-keycloak" 2>/dev/null || true; docker stop glow-keycloak 2>/dev/null; docker rm glow-keycloak 2>/dev/null; echo "✅ All services stopped"; exit 0' INT; \
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
		CLIENT_PORT=$${CLIENT_PORT:-3000}; \
		APP_PREFIX=$${APP_PREFIX:-}; \
		docker run -d --name glow-keycloak -p $(KEYCLOAK_PORT):8080 \
			-v "$(PWD)/uploads/themes:/opt/keycloak/themes:ro" \
			-e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
			-e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
			-e KC_DB=postgres \
			-e KC_DB_URL=jdbc:postgresql://host.docker.internal:5432/mydb?currentSchema=keycloak \
			-e KC_DB_USERNAME=$$DB_USER \
			-e KC_DB_PASSWORD=$$DB_PASSWORD \
		-e KC_DB_SCHEMA=keycloak \
		-e KC_PROXY=none \
		-e KC_HTTP_ENABLED=true \
		-e KC_HTTP_RELATIVE_PATH=/auth \
		-e KC_HOSTNAME=http://localhost:$(KEYCLOAK_PORT)/auth \
		-e KC_HOSTNAME_STRICT=false \
		-e KC_HOSTNAME_STRICT_BACKCHANNEL=false \
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
	(cd server && redis-server --port $(REDIS_PORT) --dir . --dbfilename dump.rdb 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;31m[REDIS]\033[0m %s' "$$line")"; done) & \
	(cd server && ( $(PWD)/$(VENV_PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port $(SERVER_PORT) --reload-exclude server/openapi.json --reload-exclude 'app/sql/types.py' --reload-exclude 'tests/sql/types.py') 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;32m[SERVER]\033[0m %s' "$$line")"; done) & \
	(cd client && yarn watch:openapi 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;36m[OPENAPI]\033[0m %s' "$$line")"; done) & \
	(cd client && yarn watch:sql-types 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;36m[SQL-TYPES]\033[0m %s' "$$line")"; done) & \
	(cd client && APP_PREFIX=$${APP_PREFIX:-}; KEYCLOAK_PUBLIC_URL=http://localhost:8080/auth NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:8080/auth NODE_OPTIONS='--dns-result-order=ipv4first' yarn dev 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;35m[CLIENT]\033[0m %s' "$$line")"; done) & \
	(cd database && READS=1 MIN_MS=0 SAMPLE_MS=150 DEBUG_READS=1 yarn logs 2>&1 | while IFS= read -r line; do echo "$$(printf '\033[0;33m[DATABASE]\033[0m %s' "$$line")"; done) & \
	wait

# Stop all services (for cleanup)
stop:
	@echo "🛑 Stopping all GLOW services..."
	@echo "Stopping Redis on port $(REDIS_PORT)..."
	@if lsof -ti:$(REDIS_PORT) >/dev/null 2>&1; then \
		kill -9 $$(lsof -ti:$(REDIS_PORT)) 2>/dev/null && echo "✅ Redis stopped" || echo "⚠️  Redis process not found"; \
	else \
		echo "⚠️  No process found on port $(REDIS_PORT)"; \
	fi
	@echo "Stopping Server on port $(SERVER_PORT)..."
	@if lsof -ti:$(SERVER_PORT) >/dev/null 2>&1; then \
		kill -9 $$(lsof -ti:$(SERVER_PORT)) 2>/dev/null && echo "✅ Server stopped" || echo "⚠️  Server process not found"; \
	else \
		echo "⚠️  No process found on port $(SERVER_PORT)"; \
	fi
	@echo "Stopping Client on port $(CLIENT_PORT)..."
	@if lsof -ti:$(CLIENT_PORT) >/dev/null 2>&1; then \
		kill -9 $$(lsof -ti:$(CLIENT_PORT)) 2>/dev/null && echo "✅ Client stopped" || echo "⚠️  Client process not found"; \
	else \
		echo "⚠️  No process found on port $(CLIENT_PORT)"; \
	fi
	@echo "Stopping Database logs..."
	@pkill -f "stream-logs.js" 2>/dev/null && echo "✅ Database logs stopped" || echo "⚠️  Database logs process not found"
	@echo "Stopping SQL types watcher..."
	@pkill -f "chokidar.*sql" 2>/dev/null && echo "✅ SQL types watcher stopped" || echo "⚠️  SQL types watcher process not found"
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
	@rm -rf server/.pytest_cache server/.mypy_cache server/.ruff_cache 2>/dev/null || true
	@rm -rf server/htmlcov server/.coverage 2>/dev/null || true
	@rm -f server/dump.rdb 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Install client dependencies
install-client:
	@echo "Installing client dependencies..."
	@cd client && yarn install
	@echo "✅ Client dependencies installed"

# Restore database from latest backup
restore-db:
	@echo "Restoring database from latest backup..."
	@cd database && yarn start
	@echo "✅ Database restored"

# Migrate database (most recent migration only) + regenerate everything
migrate-db:
	@echo "Running database migrations (most recent only)..."
	@cd database && bash scripts/start.sh --migrate
	@echo "✅ Database migrations completed"
	@echo ""
	@$(MAKE) split-schema
	@echo ""
	@echo "✅ Migration + schema split complete"

# Migrate database (most recent migration only, no regeneration)
migrate-db-only:
	@echo "Running database migrations (most recent only)..."
	@cd database && bash scripts/start.sh --migrate
	@echo "✅ Database migrations completed"

# Migrate database (all migrations)
migrate-db-all:
	@echo "Running all database migrations..."
	@cd database && yarn migrate:all
	@echo "✅ All database migrations completed"

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
	@PYTHONPATH=server DB_USER="$${DB_USER:-myuser}" \
	 DB_PASSWORD="$${DB_PASSWORD:-mypassword}" \
	 DB_NAME="$${DB_NAME:-mydb}" \
	 DB_HOST="$${DB_HOST:-localhost}" \
	 DB_PORT="$${DB_PORT:-5432}" \
	 $(VENV_PYTHON) server/scripts/generate_registry.py all
	@echo "✅ Registry generation complete"

# Validate registry files match DB state
registry-validate: check-venv
	@echo "Validating registry files..."
	@PYTHONPATH=server DB_USER="$${DB_USER:-myuser}" \
	 DB_PASSWORD="$${DB_PASSWORD:-mypassword}" \
	 DB_NAME="$${DB_NAME:-mydb}" \
	 DB_HOST="$${DB_HOST:-localhost}" \
	 DB_PORT="$${DB_PORT:-5432}" \
	 $(VENV_PYTHON) server/scripts/generate_registry.py validate
	@echo "✅ Registry validation complete"


# Connect to database
connect-db:
	@echo "Connecting to database..."
	@cd database && yarn connect
	@echo "✅ Connected to database"

# Regenerate all seed SQL files (base + all setups) via testcontainers
seed-gen: check-venv
	@echo "Regenerating all seed SQL files..."
	@PYTHONPATH=server $(VENV_PYTHON) -m database.scripts.runner --all

# Load seed data into local database
load-seeds:
	@echo "Loading seed data..."
	@bash database/scripts/load-modules.sh

# Build fresh database from schema + modules + bootstrap keys
fresh-db:
	@cd database && bash scripts/start.sh --clean-modules
	@echo ""
	@echo "To start services, run: make run"


# MCP setup for Cursor IDE
mcp: check-venv
	@echo "Setting up MCP for Cursor IDE..."
	@echo "1. Configuring Keycloak token lifespan..."
	@$(VENV_PYTHON) server/scripts/configure-mcp-token-lifespan.py || echo "⚠️  Could not configure token lifespan (Keycloak may not be running)"
	@echo "2. Getting token and updating Cursor config..."
	@$(VENV_PYTHON) scripts/setup-cursor-mcp.py
	@echo ""
	@echo "✅ MCP setup complete!"
	@echo "   - Token lifetime: $(shell $(VENV_PYTHON) -c 'import os; from dotenv import load_dotenv; load_dotenv(); print(f\"{int(os.getenv(\"MCP_TOKEN_LIFESPAN\", \"86400\")) // 3600} hours\")' 2>/dev/null || echo '24 hours') (configurable via MCP_TOKEN_LIFESPAN)"
	@echo "   - Cursor config updated at ~/.cursor/mcp.json"
	@echo "   - Restart Cursor IDE to use the new configuration"


# Show help
help:
	@echo "GLOW - Graduate Learning Orientation Workshop"
	@echo ""
	@echo "Getting started:"
	@echo "  setup          - Copy .env.example to .env"
	@echo "  deploy         - Build seed SQL, start all Docker services"
	@echo "  deploy-clean   - Same as deploy but wipes volumes first (fresh start)"
	@echo ""
	@echo "Environment setup:"
	@echo "  setup-venv   - Create virtual environment at .venv"
	@echo "  install      - Install all dependencies in venv"
	@echo "  clean        - Remove virtual environment"
	@echo ""
	@echo "Client setup:"
	@echo "  install-client - Install client dependencies with yarn"
	@echo ""
	@echo "Database:"
	@echo "  restore-db       - Restore database from latest backup"
	@echo "  migrate-db       - Run most recent database migration"
	@echo "  migrate-db-all   - Run all database migrations"
	@echo "  connect-db       - Connect to database"
	@echo "  seed-gen         - Regenerate all seed SQL files (base + all setups)"
	@echo "  fresh-db         - Build fresh DB from schema + modules + keys"
	@echo "  load-seeds       - Load seed data into local database"
	@echo ""
	@echo "Services:"
	@echo "  run          - Start all services in foreground (Ctrl+C to stop)"
	@echo "  stop         - Stop all services including Keycloak"
	@echo ""
	@echo "Code quality:"
	@echo "  format       - Format code with Ruff"
	@echo "  lint         - Run linter checks"
	@echo "  typecheck    - Run MyPy for static type checking"
	@echo "  typecheck-client - Run TypeScript type checking for client"
	@echo ""
	@echo "Testing:"
	@echo "  test         - Run server unit tests (pytest)"
	@echo "  test-cov     - Run server tests with coverage"
	@echo ""
	@echo "Build:"
	@echo "  build-client - Build client for production"
	@echo ""
	@echo "Utilities:"
	@echo "  cleanup      - Clean up generated files and cache"
	@echo "  mcp          - Setup MCP for Cursor IDE (configure Keycloak token lifespan and update Cursor config)"
	@echo ""
	@echo "Code generation:"
	@echo "  generate-tests  - Generate pytest tests"
	@echo "  openapi-gen      - Generate OpenAPI schema manually"
	@echo "  gen-client-types - Generate client TypeScript types from OpenAPI"
	@echo ""
	@echo "Service URLs:"
	@echo "  Redis:     localhost:$(REDIS_PORT)"
	@echo "  Server:    http://localhost:$(SERVER_PORT)"
	@echo "  Client:    http://localhost:$(CLIENT_PORT)"
	@echo "  Database:  localhost:$(DATABASE_PORT)"
	@echo "  Keycloak:  http://localhost:$(KEYCLOAK_PORT)"
	@echo ""
	@echo "Virtual environment location: $(VENV)"
	@echo "To activate manually: source $(VENV_BIN)/activate"
