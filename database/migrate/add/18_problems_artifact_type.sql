-- Migration: Add artifact_type column to problems_entry.
--
-- Tracks which artifact type a problem is associated with
-- (e.g. 'persona', 'scenario', 'activity'). Backfill existing
-- rows with 'activity' since all existing problems come from
-- the activity flow.
--
-- Steps:
--   1. Add artifact_type column to problems_entry
--   2. Backfill NULLs with 'activity'
--   3. Set default and NOT NULL
--   4. Recreate problems_mv to include artifact_type

-- ============================================================================
-- Step 1: Add artifact_type column
-- ============================================================================

ALTER TABLE public.problems_entry
    ADD COLUMN artifact_type public.artifact_type;

-- ============================================================================
-- Step 2: Backfill existing rows
-- ============================================================================

UPDATE public.problems_entry
SET artifact_type = 'activity'
WHERE artifact_type IS NULL;

-- ============================================================================
-- Step 3: Set default and NOT NULL
-- ============================================================================

ALTER TABLE public.problems_entry
    ALTER COLUMN artifact_type SET DEFAULT 'activity',
    ALTER COLUMN artifact_type SET NOT NULL;

-- ============================================================================
-- Step 4: Recreate problems_mv to include artifact_type
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS public.problems_mv;

CREATE MATERIALIZED VIEW public.problems_mv AS
SELECT
    pe.id AS problem_id,
    ppc.profiles_id AS profile_id,
    pe.type::text AS type,
    pe.message,
    COALESCE(re.resolved, false) AS resolved,
    pe.created_at,
    pe.active,
    pe.mcp,
    pe.generated,
    pe.artifact_type
FROM public.problems_entry pe
LEFT JOIN public.profiles_problems_connection ppc ON ppc.problem_id = pe.id
LEFT JOIN LATERAL (
    SELECT resolves_entry.resolved
    FROM public.resolves_entry
    WHERE resolves_entry.problem_id = pe.id
      AND resolves_entry.active = true
    ORDER BY resolves_entry.created_at DESC
    LIMIT 1
) re ON true
WHERE pe.active = true
WITH NO DATA;

CREATE UNIQUE INDEX problems_mv_problem_id_idx ON public.problems_mv (problem_id);

REFRESH MATERIALIZED VIEW public.problems_mv;
