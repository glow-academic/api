-- Migration: Create refresh_entry table for MV refresh tracking.
--
-- Append-only record of MV refreshes. operation_key groups entries from
-- the same operation. Enables per-target throttling and system of record.

CREATE TABLE IF NOT EXISTS public.refresh_entry (
    id uuid DEFAULT uuidv7() PRIMARY KEY,
    operation_key uuid NOT NULL,
    artifact_type public.artifact_type NOT NULL,
    target text NOT NULL,
    session_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    active boolean DEFAULT true NOT NULL,
    generated boolean DEFAULT false NOT NULL,
    mcp boolean DEFAULT false NOT NULL
);

-- Index for grouping by operation
CREATE INDEX IF NOT EXISTS idx_refresh_entry_operation_key ON public.refresh_entry (operation_key);

-- Index for per-target throttling (most recent refresh per target)
CREATE INDEX IF NOT EXISTS idx_refresh_entry_target_created ON public.refresh_entry (target, created_at DESC);
