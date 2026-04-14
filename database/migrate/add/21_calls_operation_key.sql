-- Migration: Add operation_key to calls_entry and rebuild calls_mv.
--
-- operation_key is a universal key stored on every call:
--   - For WRITE operations: serves as idempotency key (enables soft/promote via upsert)
--   - For READ operations: serves as snapshot key (enables playback of stored responses)

-- 1. Add column with default for backfill
ALTER TABLE public.calls_entry
    ADD COLUMN IF NOT EXISTS operation_key uuid NOT NULL DEFAULT uuidv7();

-- 2. Remove the default (callers must always provide going forward)
ALTER TABLE public.calls_entry
    ALTER COLUMN operation_key DROP DEFAULT;

-- 3. Rebuild calls_mv to include operation_key
DROP MATERIALIZED VIEW IF EXISTS public.calls_mv CASCADE;

CREATE MATERIALIZED VIEW public.calls_mv AS
 SELECT c.id AS call_id,
    c.run_id,
    c.created_at AS call_created_at,
    c.operation_key,
    ue.id AS upload_id,
    ue.file_path,
    ue.mime_type,
    tcc.tools_id AS tool_id
   FROM (((public.calls_entry c
     LEFT JOIN public.call_uploads_entry cue ON (((cue.call_id = c.id) AND (cue.active = true))))
     LEFT JOIN public.uploads_entry ue ON (((ue.id = cue.upload_id) AND (ue.active = true))))
     LEFT JOIN public.tools_calls_connection tcc ON ((tcc.call_id = c.id)))
  WHERE (c.run_id IS NOT NULL)
  WITH NO DATA;

-- 4. Recreate unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX calls_mv_call_id_idx ON public.calls_mv USING btree (call_id);

