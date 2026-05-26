-- Eval-mode tag on soft_calls_entry.
--
-- Trace-driven benchmark runs ("eval mode") dispatch tools live with
-- ``soft=True`` so writes land dormant. The new ``eval`` column tags
-- the resulting ledger rows so UI surfaces filter them out of normal
-- pending-state listings — dormant eval writes never appear as
-- actionable items in the user's view. See:
--   * core/app/infra/generation/prepare.py    (sets PrepareGenerationResult.eval)
--   * core/app/infra/generation/execute.py    (flips the contextvar)
--   * core/app/infra/events/eval_context.py   (PEP 567 contextvar)
--   * core/app/tools/entries/soft_calls/create.py  (writes the column)
--   * core/app/tools/entries/soft_calls/search.py  (filters via include_eval)
--
-- Safe to run on a live DB: additive column with a DEFAULT, no
-- rewrites, no locking concerns at our row counts. The MV recreate is
-- the only mild blip (cache miss until refresh) — re-indexed inline.

BEGIN;

-- 1. Add the column. DEFAULT false on existing rows; NOT NULL going forward.
ALTER TABLE public.soft_calls_entry
    ADD COLUMN IF NOT EXISTS eval boolean NOT NULL DEFAULT false;

-- 2. Rebuild the MV with the eval column exposed. Postgres has no
--    CREATE OR REPLACE for materialized views, so drop + recreate.
--    Indexes recreated inline so search_soft_calls keeps its seek.
DROP MATERIALIZED VIEW IF EXISTS public.soft_calls_mv;

CREATE MATERIALIZED VIEW public.soft_calls_mv AS
 SELECT DISTINCT ON (call_id) id AS soft_call_entry_id,
    call_id,
    artifact,
    operation,
    status,
    artifact_id,
    patch,
    eval,
    created_at
   FROM public.soft_calls_entry s
  WHERE (active = true)
  ORDER BY call_id, created_at DESC
  WITH NO DATA;

CREATE UNIQUE INDEX idx_soft_calls_mv_call
    ON public.soft_calls_mv USING btree (call_id);

CREATE INDEX idx_soft_calls_mv_target
    ON public.soft_calls_mv USING btree (artifact, artifact_id, status);

-- 3. Populate the MV so reads don't return empty until the next refresh.
REFRESH MATERIALIZED VIEW public.soft_calls_mv;

COMMIT;
