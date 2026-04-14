-- Migration: Create refresh_mv materialized view.

CREATE MATERIALIZED VIEW public.refresh_mv AS
 SELECT r.id,
    r.operation_key,
    r.artifact_type,
    r.target,
    r.session_id,
    r.created_at,
    r.active,
    r.generated,
    r.mcp
   FROM public.refresh_entry r
  WHERE (r.active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX refresh_mv_id_idx ON public.refresh_mv USING btree (id);
