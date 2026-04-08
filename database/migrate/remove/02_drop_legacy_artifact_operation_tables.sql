-- ══════════════════════════════════════════════════════════════
-- Rollback Migration 02: Restore legacy artifact/operation tables
-- ══════════════════════════════════════════════════════════════

-- 1. Restore legacy columns on tools_resource
ALTER TABLE tools_resource ADD COLUMN IF NOT EXISTS operation TEXT;
ALTER TABLE tools_resource ADD COLUMN IF NOT EXISTS artifacts TEXT[] NOT NULL DEFAULT '{}';

-- 2. Restore legacy column on roles_resource
ALTER TABLE roles_resource ADD COLUMN IF NOT EXISTS artifacts artifact_type[] NOT NULL DEFAULT '{}';

-- 3. Restore lookup tables
CREATE TABLE IF NOT EXISTS artifacts_resource (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    artifact TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT true,
    generated BOOLEAN NOT NULL DEFAULT false,
    mcp BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operations_resource (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    operation operation_type NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT true,
    generated BOOLEAN NOT NULL DEFAULT false,
    mcp BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Restore tool junctions
CREATE TABLE IF NOT EXISTS tool_artifacts_junction (
    tool_id UUID NOT NULL REFERENCES tool_artifact(id) ON DELETE CASCADE,
    artifacts_id UUID NOT NULL REFERENCES artifacts_resource(id) ON DELETE CASCADE,
    active BOOLEAN NOT NULL DEFAULT true,
    generated BOOLEAN NOT NULL DEFAULT false,
    mcp BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tool_id, artifacts_id)
);

CREATE TABLE IF NOT EXISTS tool_operations_junction (
    tool_id UUID NOT NULL REFERENCES tool_artifact(id),
    operations_id UUID NOT NULL REFERENCES operations_resource(id),
    active BOOLEAN NOT NULL DEFAULT true,
    generated BOOLEAN NOT NULL DEFAULT false,
    mcp BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tool_id, operations_id)
);

-- 5. Track rollback
INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (2, '02_drop_legacy_artifact_operation_tables.sql', 'remove')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
