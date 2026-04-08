-- ══════════════════════════════════════════════════════════════
-- Rollback Migration 01: Remove permissions_resource
-- ══════════════════════════════════════════════════════════════

-- 1. Drop tool permissions junction
DROP TABLE IF EXISTS tool_permissions_junction;

-- 2. Drop permission_ids from tools_resource
ALTER TABLE tools_resource DROP COLUMN IF EXISTS permission_ids;

-- 3. Drop permission_ids from roles_resource
ALTER TABLE roles_resource DROP COLUMN IF EXISTS permission_ids;

-- 4. Drop permissions_resource
DROP TABLE IF EXISTS permissions_resource;

-- 5. Track rollback
INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (1, '01_permissions_resource.sql', 'remove')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
