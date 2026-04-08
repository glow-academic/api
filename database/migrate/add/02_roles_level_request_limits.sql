-- ══════════════════════════════════════════════════════════════
-- Migration 02 (add): Roles level + request limits on roles
--
-- Safe, additive operations only.
--
-- 1. Add level to roles_resource (replaces hardcoded ROLE_LEVEL)
-- 2. Add request_limit_ids to roles_resource (role-level rate limits)
-- 3. Add role_id to profiles_resource (replaces role enum string)
-- 4. Enhance request_limits_resource with interval + rename column
-- ══════════════════════════════════════════════════════════════

-- 1. Role hierarchy level (0 = highest privilege)
ALTER TABLE roles_resource ADD COLUMN IF NOT EXISTS level INTEGER NOT NULL DEFAULT 99;

-- 2. Role-level request limits (references request_limits_resource)
ALTER TABLE roles_resource ADD COLUMN IF NOT EXISTS request_limit_ids UUID[] NOT NULL DEFAULT '{}';

-- 3. Direct role reference on profiles (replaces denormalized role string)
ALTER TABLE profiles_resource ADD COLUMN IF NOT EXISTS role_id UUID;

-- 4. Enhance request_limits_resource
--    Rename requests_per_day → "limit" (generic count)
--    Add interval column (native Postgres INTERVAL type)
ALTER TABLE request_limits_resource RENAME COLUMN requests_per_day TO "limit";
ALTER TABLE request_limits_resource ADD COLUMN IF NOT EXISTS "interval" INTERVAL NOT NULL DEFAULT INTERVAL '1 day';

-- 5. Add unique constraint on name (replaces old UNIQUE(role, name))
ALTER TABLE roles_resource ADD CONSTRAINT roles_resource_name_unique UNIQUE (name);

-- 6. Track migration
INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (2, '02_roles_level_request_limits.sql', 'add')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
