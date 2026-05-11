-- v2.15.35_02_sessions_mv_department_ids.sql
--
-- Project ``department_ids`` onto ``sessions_mv`` so the pricing
-- (and any future per-session) department filter can resolve
-- session_ids → department_ids without a runtime junction join.
--
-- Sessions don't carry departments directly — the department comes
-- from the owning profile via ``profile_departments_junction``. We
-- aggregate per profile_id and surface as an array column on the MV.
-- The existing UNIQUE INDEX on ``session_id`` keeps holding because
-- the LEFT JOIN preserves the (session_id, profile_id) row shape.

DROP MATERIALIZED VIEW IF EXISTS public.sessions_mv CASCADE;

CREATE MATERIALIZED VIEW public.sessions_mv AS
 WITH profile_dep_agg AS (
        SELECT pdj.profile_id,
               array_agg(DISTINCT pdj.departments_id ORDER BY pdj.departments_id) AS department_ids
          FROM public.profile_departments_junction pdj
         GROUP BY pdj.profile_id
      )
 SELECT s.id AS session_id,
    psc.profiles_id AS profile_id,
    s.created_at AS session_created_at,
    s.active,
    s.mcp,
    COALESCE(pda.department_ids, ARRAY[]::uuid[]) AS department_ids
   FROM (public.sessions_entry s
     JOIN public.profiles_sessions_connection psc ON ((psc.session_id = s.id))
     LEFT JOIN profile_dep_agg pda ON ((pda.profile_id = psc.profiles_id)))
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_mv_session_id
    ON public.sessions_mv USING btree (session_id);

REFRESH MATERIALIZED VIEW public.sessions_mv;
