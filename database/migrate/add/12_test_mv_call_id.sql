-- Migration: Add call_id to test_mv so black-box get_tests can
-- derive run_id without inline SQL (test → call → run chain).

DROP MATERIALIZED VIEW IF EXISTS public.test_mv;

CREATE MATERIALIZED VIEW public.test_mv AS
 WITH eval_links AS (
         SELECT c.attempt_id AS test_id,
            (array_agg(c.evals_id ORDER BY c.created_at))[1] AS eval_id
           FROM public.test_evals_connection c
          WHERE (c.active = true)
          GROUP BY c.attempt_id
        ), profile_links AS (
         SELECT c.attempt_id AS test_id,
            (array_agg(c.profiles_id ORDER BY c.created_at))[1] AS profile_id
           FROM public.test_profiles_connection c
          WHERE (c.active = true)
          GROUP BY c.attempt_id
        ), department_links AS (
         SELECT c.attempt_id AS test_id,
            array_agg(DISTINCT c.departments_id) FILTER (WHERE (c.departments_id IS NOT NULL)) AS department_ids
           FROM public.test_departments_connection c
          WHERE (c.active = true)
          GROUP BY c.attempt_id
        )
 SELECT t.id AS test_id,
    t.call_id,
    el.eval_id,
    pl.profile_id,
    COALESCE(dl.department_ids, ARRAY[]::uuid[]) AS department_ids,
    t.name AS test_name,
    t.description AS test_description,
    t.num_invocations,
    t.infinite_mode,
    t.is_dynamic,
    COALESCE(ba_archive.archived, false) AS archived,
    t.created_at AS test_created_at
   FROM ((((public.test_entry t
     LEFT JOIN eval_links el ON ((el.test_id = t.id)))
     LEFT JOIN profile_links pl ON ((pl.test_id = t.id)))
     LEFT JOIN department_links dl ON ((dl.test_id = t.id)))
     LEFT JOIN LATERAL ( SELECT test_archive_entry.archived
           FROM public.test_archive_entry
          WHERE ((test_archive_entry.test_id = t.id) AND (test_archive_entry.active = true))
          ORDER BY test_archive_entry.created_at DESC
         LIMIT 1) ba_archive ON (true))
  WHERE (t.active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX test_mv_test_id_idx ON public.test_mv (test_id);

REFRESH MATERIALIZED VIEW public.test_mv;
