-- ══════════════════════════════════════════════════════════════
-- Migration 01: Add permissions_resource for RBAC
--
-- Replaces:
--   - roles_resource.artifacts (flat artifact array)
--   - artifacts_resource (lookup table)
--   - operations_resource (lookup table)
--   - tool_artifacts_junction + tool_operations_junction
--
-- Each permission is a unique (artifact, operation) tuple like
-- "scenario.create" or "attempt.grade". Roles and tools link
-- to permissions via UUID arrays on their resource tables.
-- ══════════════════════════════════════════════════════════════

-- 1. Create permissions_resource
CREATE TABLE IF NOT EXISTS permissions_resource (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    artifact artifact_type NOT NULL,
    operation operation_type NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT true,
    generated BOOLEAN NOT NULL DEFAULT false,
    mcp BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT permissions_resource_unique UNIQUE (artifact, operation)
);

-- 2. Add permission_ids to roles_resource (replaces artifacts array)
ALTER TABLE roles_resource ADD COLUMN IF NOT EXISTS permission_ids UUID[] NOT NULL DEFAULT '{}';

-- 3. Add permission_ids to tools_resource (replaces operation + artifacts)
ALTER TABLE tools_resource ADD COLUMN IF NOT EXISTS permission_ids UUID[] NOT NULL DEFAULT '{}';

-- 4. Create tool_permissions_junction (replaces tool_artifacts + tool_operations)
CREATE TABLE IF NOT EXISTS tool_permissions_junction (
    tool_id UUID NOT NULL,
    permissions_id UUID NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    generated BOOLEAN NOT NULL DEFAULT false,
    mcp BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tool_id, permissions_id),
    FOREIGN KEY (tool_id) REFERENCES tool_artifact(id) ON DELETE CASCADE,
    FOREIGN KEY (permissions_id) REFERENCES permissions_resource(id) ON DELETE CASCADE
);

-- 5. Create tool_drafts_permissions_connection (replaces artifacts + operations connections)
CREATE TABLE IF NOT EXISTS tool_drafts_permissions_connection (
    draft_id UUID NOT NULL,
    permissions_id UUID NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    generated BOOLEAN NOT NULL DEFAULT false,
    mcp BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (draft_id, permissions_id)
);

-- 6. Track migration
INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (1, '01_permissions_resource.sql', 'add')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
