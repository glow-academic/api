# Database Management

This directory contains all database-related operations for the Glow project.

## Source of Truth

- **Schema**: `schema/` — structured SQL files (extensions, functions, enums, tables, indexes, views, etc.)
- **Seed data**: `seeds/` — static Python data definitions, `output/` — generated SQL from runner
- **Migrations**: `migrate/` — incremental DDL changes

## Workflow

### 1. Default Start (Latest Backup)
```bash
make restore-db
```
- Finds the latest backup from `history/` folder
- Restores the backup to a fresh database

### 2. Fresh Start
```bash
make fresh-db
```
Builds a fresh database from schema + seed modules + bootstrap keys.

### 3. Load Seeds
```bash
make load-seeds
```
Loads seed data into the local database using `load-modules.sh`.

### 4. Migration Mode
```bash
make migrate-db       # Apply + regenerate schema
make migrate-db-only  # Apply only, no regeneration
```

### 5. Connect to Database
```bash
make connect-db
```

## Directory Structure

```
database/
├── schema/                 # Structured DDL schema files
│   ├── extensions.sql
│   ├── functions.sql
│   ├── enums/
│   ├── tables/
│   ├── indexes/
│   ├── foreign_keys/
│   └── views/
├── seeds/                  # Static seed data (Python)
│   ├── tools.py            # Tool definitions (regenerate with scripts/generate_tools.py)
│   ├── auths.py            # Auth provider definitions
│   └── setups/             # Setup-specific seed data
│       ├── organization/
│       └── university/
├── scripts/                # Runtime utilities
│   ├── runner.py           # Seed runner orchestrator
│   ├── generate_tools.py   # Tool definition generator
│   ├── load-modules.sh     # Assembled seed SQL loader
│   ├── bootstrap-keys.sh   # API key encryption and injection
│   └── start.sh            # Database management (start/migrate/backup)
├── output/                 # Generated pg_dump seed files
│   ├── base-seed.sql
│   └── setups/
├── migrate/                # Migration SQL files
├── history/                # Database backups (auto-created)
└── package.json
```

## Migration Workflow

1. Find next migration number: `ls database/migrate/ | sort -n | tail -1`
2. Create migration file: `database/migrate/{next_number}_{desc}.sql`
3. Apply: `make migrate-db`

## Environment Variables

All configuration is via `.env` (copy from `.env.example`):

- `DB_USER` — Database user (default: myuser)
- `DB_PASSWORD` — Database password (default: mypassword)
- `DB_NAME` — Database name (default: glowapi)
- `DB_HOST` — Database host (default: localhost)
- `DB_PORT` — Database port (default: 5432)
- `SECRET_KEY` — Required for encrypting API keys and secrets
- `SEED_SETUP` — Setup to load: "university" (default) or "organization"
