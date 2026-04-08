-- ══════════════════════════════════════════════════════════════
-- Migration 02: Drop legacy artifact/operation tables and columns
--
-- Now that permissions_resource replaces the old system:
--   - artifacts_resource → permissions_resource.artifact enum
--   - operations_resource → permissions_resource.operation enum
--   - tool_artifacts_junction → tool_permissions_junction
--   - tool_operations_junction → tool_permissions_junction
--   - roles_resource.artifacts → roles_resource.permission_ids
--   - tools_resource.operation + artifacts → tools_resource.permission_ids
-- ══════════════════════════════════════════════════════════════

-- 1. Drop tool legacy junctions
DROP TABLE IF EXISTS tool_artifacts_junction;
DROP TABLE IF EXISTS tool_operations_junction;

-- 2. Drop legacy lookup tables
DROP TABLE IF EXISTS artifacts_resource;
DROP TABLE IF EXISTS operations_resource;

-- 3. Drop legacy columns from roles_resource
ALTER TABLE roles_resource DROP COLUMN IF EXISTS artifacts;

-- 4. Drop legacy columns from tools_resource
ALTER TABLE tools_resource DROP COLUMN IF EXISTS operation;
ALTER TABLE tools_resource DROP COLUMN IF EXISTS artifacts;

-- 5. Track migration
INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (2, '02_drop_legacy_artifact_operation_tables.sql', 'add')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
