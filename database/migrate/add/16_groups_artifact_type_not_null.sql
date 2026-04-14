-- Migration: Make artifact_type NOT NULL on groups_entry.
--
-- Since the fresh template has no pre-existing groups, we can safely
-- backfill any NULLs with 'persona' as a default and add the constraint.
--
-- Steps:
--   1. Backfill NULL artifact_type with 'persona'
--   2. Set default to 'persona'
--   3. Add NOT NULL constraint

-- ============================================================================
-- Step 1: Backfill NULLs
-- ============================================================================

UPDATE public.groups_entry
SET artifact_type = 'persona'
WHERE artifact_type IS NULL;

-- ============================================================================
-- Step 2: Set default
-- ============================================================================

ALTER TABLE public.groups_entry
    ALTER COLUMN artifact_type SET DEFAULT 'persona';

-- ============================================================================
-- Step 3: Add NOT NULL constraint
-- ============================================================================

ALTER TABLE public.groups_entry
    ALTER COLUMN artifact_type SET NOT NULL;
