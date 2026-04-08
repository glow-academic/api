-- ══════════════════════════════════════════════════════════════
-- Migration 02 (remove): Drop legacy role enum + profile request limit junctions
--
-- Destructive operations — apply after verifying add migration works.
-- ══════════════════════════════════════════════════════════════

-- 1. Drop role enum column from roles_resource (name + level is sufficient)
ALTER TABLE roles_resource DROP COLUMN IF EXISTS role;

-- 2. Drop role string from profiles_resource (replaced by role_id)
ALTER TABLE profiles_resource DROP COLUMN IF EXISTS role;

-- 3. Drop profile-level request limit junctions (limits are now on roles)
DROP TABLE IF EXISTS profile_request_limits_junction;
DROP TABLE IF EXISTS profile_drafts_request_limits_connection;

-- 4. Track migration
INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (2, '02_roles_level_request_limits.sql', 'remove')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
