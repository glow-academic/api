-- Migration: backfill primary_departments_resource + junction from legacy
-- departments_resource.is_primary flag.
--
-- Strategy:
--   1. For every department flagged is_primary=true, create a matching
--      primary_departments_resource row (one per department). Uses ON
--      CONFLICT (departments_id) DO NOTHING so re-runs are no-ops.
--
--   2. For every profile that has one of those departments in its
--      profile_departments_junction, bind it to the matching
--      primary_departments_resource row via
--      profile_primary_departments_junction. Only inserts when the profile
--      has no primary already (ON CONFLICT (profile_id) DO NOTHING).
--
-- Guarded: the whole block is a no-op if is_primary has already been
-- dropped (fresh DBs from schema.sql, or DBs past the v2.15.15_03 drop).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'departments_resource'
          AND column_name = 'is_primary'
    ) THEN
        RETURN;
    END IF;

    INSERT INTO public.primary_departments_resource (id, departments_id, active, generated, mcp)
    SELECT uuidv7(), d.id, true, false, false
    FROM public.departments_resource d
    WHERE d.is_primary = true
    ON CONFLICT (departments_id) DO NOTHING;

    INSERT INTO public.profile_primary_departments_junction
        (profile_id, primary_departments_id, active, generated, mcp)
    SELECT DISTINCT ON (pd.profile_id)
        pd.profile_id,
        pdr.id,
        true,
        false,
        false
    FROM public.profile_departments_junction pd
    JOIN public.departments_resource d ON d.id = pd.departments_id
    JOIN public.primary_departments_resource pdr ON pdr.departments_id = d.id
    WHERE pd.active = true
      AND d.is_primary = true
    ORDER BY pd.profile_id, pd.created_at ASC
    ON CONFLICT (profile_id) DO NOTHING;
END $$;
