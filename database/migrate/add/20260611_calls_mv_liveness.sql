-- calls_mv own-row liveness filter (soft-delete leak fix).
--
-- calls_mv filtered its JOINED uploads (call_uploads_entry.active,
-- uploads_entry.active) but NOT its own calls_entry.active, and its only
-- WHERE predicate (c.run_id IS NOT NULL) is vacuous because calls_entry.run_id
-- is NOT NULL. calls/create.py writes `active = not soft`, so un-acked /
-- rejected soft-calls (active = false) plus their upload file_path / mime_type
-- leaked into this hot read. Every sibling MV that fronts a soft-deletable
-- *_entry table carries `WHERE active = true` (audios_mv, files_mv, images_mv,
-- videos_mv, texts_mv, soft_calls_mv); this mirrors that and the D1
-- attempt_analysis_mv liveness fix.
--
-- Readers affected: core/app/tools/entries/calls/{search,get}.py both query
-- calls_mv and bypass-inline the MV definition via resolve_mv_source, so the
-- filter must live in the MV body to cover the bypass path too.
--
-- Postgres has no CREATE OR REPLACE for materialized views, so drop + recreate.
-- The unique index calls_mv_call_id_idx (required for REFRESH ... CONCURRENTLY)
-- and idx_calls_mv_operation_key are dropped by the cascade and recreated
-- inline. The active filter only removes rows (never duplicates) so call_id
-- stays unique.
--
-- Safe on a live DB: read-only redefinition, the only blip is a cache miss
-- until the inline REFRESH below repopulates it.

BEGIN;

DROP MATERIALIZED VIEW IF EXISTS public.calls_mv;

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
  WHERE ((c.active = true) AND (c.run_id IS NOT NULL))
  WITH NO DATA;

CREATE UNIQUE INDEX calls_mv_call_id_idx ON public.calls_mv USING btree (call_id);

CREATE INDEX idx_calls_mv_operation_key ON public.calls_mv USING btree (operation_key);

REFRESH MATERIALIZED VIEW public.calls_mv;

COMMIT;
