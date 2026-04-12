-- Migration: Add group_names_entry table + MV for dynamic group naming.
--
-- Replaces the mutable groups_entry.name column with an append-only
-- entry table. Supports dynamic renames (e.g. AI-generated conversation
-- titles that evolve as the conversation progresses).
--
-- Steps:
--   1. Create group_names_entry table
--   2. Migrate existing names from groups_entry into group_names_entry
--   3. Create group_names_mv (latest name per group)
--   4. Recreate groups_mv to join name from group_names_mv
--   5. Drop name column from groups_entry

-- ============================================================================
-- Step 1: Create group_names_entry
-- ============================================================================

CREATE TABLE public.group_names_entry (
    id         uuid                     NOT NULL DEFAULT uuidv7(),
    group_id   uuid                     NOT NULL,
    name       text                     NOT NULL DEFAULT '',
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    active     boolean                  NOT NULL DEFAULT true,
    generated  boolean                  NOT NULL DEFAULT false,
    mcp        boolean                  NOT NULL DEFAULT false,
    session_id uuid                     NOT NULL,

    CONSTRAINT group_names_entry_pkey PRIMARY KEY (id),
    CONSTRAINT group_names_entry_group_id_fkey
        FOREIGN KEY (group_id) REFERENCES public.groups_entry(id) ON DELETE CASCADE
);

CREATE INDEX idx_group_names_entry_group_id ON public.group_names_entry (group_id);
CREATE INDEX idx_group_names_entry_created_at ON public.group_names_entry (created_at);

-- ============================================================================
-- Step 2: Migrate existing names
-- ============================================================================

INSERT INTO public.group_names_entry (group_id, name, created_at, session_id)
SELECT g.id, g.name, g.created_at, g.session_id
FROM public.groups_entry g
WHERE g.name IS NOT NULL AND g.name != '';

-- ============================================================================
-- Step 3: Create group_names_mv (latest name per group)
-- ============================================================================

CREATE MATERIALIZED VIEW public.group_names_mv AS
SELECT DISTINCT ON (gn.group_id)
    gn.id,
    gn.group_id,
    gn.name,
    gn.created_at,
    gn.generated,
    gn.mcp
FROM public.group_names_entry gn
WHERE gn.active = true
ORDER BY gn.group_id, gn.created_at DESC
WITH NO DATA;

CREATE UNIQUE INDEX group_names_mv_group_id_idx ON public.group_names_mv (group_id);
CREATE INDEX group_names_mv_id_idx ON public.group_names_mv (id);

REFRESH MATERIALIZED VIEW public.group_names_mv;

-- ============================================================================
-- Step 4: Recreate groups_mv to join name from group_names_mv
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
    g.generated
FROM public.groups_entry g
LEFT JOIN public.group_names_mv gn ON gn.group_id = g.id
WHERE g.active = true
WITH NO DATA;

CREATE UNIQUE INDEX groups_mv_group_id_idx ON public.groups_mv (group_id);
CREATE INDEX groups_mv_session_id_idx ON public.groups_mv (session_id);

REFRESH MATERIALIZED VIEW public.groups_mv;

-- ============================================================================
-- Step 5: Drop name column from groups_entry
-- ============================================================================

ALTER TABLE public.groups_entry DROP COLUMN name;
