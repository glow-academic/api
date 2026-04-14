-- Migration: Rename refresh_entry → refreshes_entry, refresh_mv → refreshes_mv.

ALTER TABLE IF EXISTS public.refresh_entry RENAME TO refreshes_entry;
ALTER INDEX IF EXISTS refresh_entry_pkey RENAME TO refreshes_entry_pkey;
ALTER INDEX IF EXISTS idx_refresh_entry_operation_key RENAME TO idx_refreshes_entry_operation_key;
ALTER INDEX IF EXISTS idx_refresh_entry_target_created RENAME TO idx_refreshes_entry_target_created;

DROP MATERIALIZED VIEW IF EXISTS public.refresh_mv CASCADE;

CREATE MATERIALIZED VIEW public.refreshes_mv AS
 SELECT r.id,
    r.operation_key,
    r.artifact_type,
    r.target,
    r.session_id,
    r.created_at,
    r.active,
    r.generated,
    r.mcp
   FROM public.refreshes_entry r
  WHERE (r.active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX refreshes_mv_id_idx ON public.refreshes_mv USING btree (id);
