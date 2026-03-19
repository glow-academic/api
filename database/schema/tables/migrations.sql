-- Migrations schema — tracks applied schema migrations (separate from app data)

CREATE SCHEMA IF NOT EXISTS migrations;

CREATE TABLE IF NOT EXISTS migrations.applied (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(20) NOT NULL,
    number INTEGER NOT NULL,
    type VARCHAR(10) NOT NULL DEFAULT 'add' CHECK (type IN ('add', 'remove')),
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT migrations_unique UNIQUE (version, number, type)
);

CREATE INDEX IF NOT EXISTS idx_migrations_version ON migrations.applied (version);
