-- attempt_analysis_mv liveness filter (soft-delete leak fix).
--
-- attempt_analysis_mv read straight from public.attempt_analysis_entry with no
-- WHERE clause, so soft-deleted / dormant rows (active = false) leaked into
-- analysis reads. Every sibling MV that fronts a soft-deletable *_entry table
-- carries `WHERE active = true` (e.g. attempt_completion_mv, benchmark_mv,
-- soft_calls_mv, test_completion_mv); attempt_analysis_entry has the same
-- `active boolean NOT NULL DEFAULT true` column but the MV omitted the filter.
--
-- Readers affected: core/app/tools/entries/attempt_analysis/{search,get}.py
-- (both query attempt_analysis_mv; search.py also bypass-inlines the MV
-- definition via resolve_mv_source, so the filter must live in the MV body to
-- cover the bypass path too).
--
-- Postgres has no CREATE OR REPLACE for materialized views, so drop + recreate.
-- The unique index idx_attempt_analysis_mv_analysis_id (required for REFRESH
-- ... CONCURRENTLY) is dropped by the cascade and recreated inline. analysis_id
-- is the projection of attempt_analysis_entry.id (PRIMARY KEY) so it stays
-- unique and never null after the active filter.
--
-- Safe on a live DB: read-only redefinition, the only blip is a cache miss
-- until the inline REFRESH below repopulates it.

BEGIN;

DROP MATERIALIZED VIEW IF EXISTS public.attempt_analysis_mv;

CREATE MATERIALIZED VIEW public.attempt_analysis_mv AS
 SELECT id AS analysis_id,
    grade_id,
    content,
    created_at
   FROM public.attempt_analysis_entry ae
  WHERE (active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX idx_attempt_analysis_mv_analysis_id
    ON public.attempt_analysis_mv USING btree (analysis_id);

REFRESH MATERIALIZED VIEW public.attempt_analysis_mv;

COMMIT;
