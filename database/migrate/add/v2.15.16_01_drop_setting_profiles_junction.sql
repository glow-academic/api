-- Migration: drop setting_profiles_junction + setting_drafts_profiles_connection.
--
-- These tables existed but were never written to (0 rows in both) and had
-- no callers that read profile-ownership on settings. The role that was
-- nominally this junction's is now owned by the logins picker
-- (setting_logins_junction → logins_resource.profile_id). profiles is a
-- pure catalog consumed by the Logins picker; there's nothing for
-- setting_profiles_* to carry.
--
-- Idempotent: DROP TABLE IF EXISTS is a no-op on fresh DBs that already
-- seeded from schema.sql without these tables (post-schema-sync).

DROP TABLE IF EXISTS public.setting_drafts_profiles_connection CASCADE;
DROP TABLE IF EXISTS public.setting_profiles_junction CASCADE;
