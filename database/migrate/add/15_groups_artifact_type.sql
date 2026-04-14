-- Migration: Add artifact_type column to groups_entry.
--
-- Tracks which artifact type a generation group is associated with
-- (e.g. 'persona', 'scenario'). Nullable — existing groups predate
-- per-artifact generation and have no artifact_type.
--
-- Steps:
--   1. Add artifact_type column to groups_entry
--   2. Recreate groups_mv to include artifact_type

-- ============================================================================
-- Step 1: Add artifact_type column to groups_entry
-- ============================================================================

ALTER TABLE public.groups_entry
    ADD COLUMN artifact_type public.artifact_type;

-- ============================================================================
-- Step 2: Recreate groups_mv to include artifact_type
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS public.groups_mv;

CREATE MATERIALIZED VIEW public.groups_mv AS
SELECT
    g.id AS group_id,
    g.session_id,
    g.created_at,
    COALESCE(gn.name, '') AS name,
    g.active,
    g.mcp,
    g.generated,
    g.artifact_type
FROM public.groups_entry g
LEFT JOIN public.group_names_mv gn ON gn.group_id = g.id
WHERE g.active = true
WITH NO DATA;

CREATE UNIQUE INDEX groups_mv_group_id_idx ON public.groups_mv (group_id);
CREATE INDEX groups_mv_session_id_idx ON public.groups_mv (session_id);

REFRESH MATERIALIZED VIEW public.groups_mv;
