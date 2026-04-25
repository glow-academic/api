-- Migration: drop the legacy departments_resource.is_primary column.
--
-- Primary-department designation now lives in primary_departments_resource +
-- profile_primary_departments_junction (see v2.15.15_01/02). The
-- departments_resource table no longer needs per-row global state for
-- "is this the primary?" — that was a per-profile question miscoded as a
-- global flag.
--
-- Idempotent via information_schema check. Must run after _02 so the
-- backfill still has is_primary to read from.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'departments_resource'
          AND column_name = 'is_primary'
    ) THEN
        ALTER TABLE public.departments_resource
            DROP COLUMN is_primary;
    END IF;
END $$;
