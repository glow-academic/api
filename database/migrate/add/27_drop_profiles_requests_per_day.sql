-- ══════════════════════════════════════════════════════════════
-- Migration 27 (add): Drop requests_per_day from profiles_resource
--
-- Request limits are now derived from roles (roles_resource.request_limit_ids)
-- instead of being denormalized on profiles_resource.
-- ══════════════════════════════════════════════════════════════

ALTER TABLE profiles_resource DROP COLUMN IF EXISTS requests_per_day;

-- Track migration
INSERT INTO migration_tracking (migration_number, migration_file, migration_type) VALUES
  (27, '27_drop_profiles_requests_per_day.sql', 'add')
ON CONFLICT (migration_number, migration_type) DO NOTHING;
