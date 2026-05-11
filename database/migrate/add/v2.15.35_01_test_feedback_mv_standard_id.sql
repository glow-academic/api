-- v2.15.35_01_test_feedback_mv_standard_id.sql
--
-- Project ``standard_id`` onto ``test_feedback_mv`` via the shared
-- ``feedbacks_standards_connection`` table, mirroring the attempt
-- feedback MV. This unblocks the benchmark graded-view path
-- (TableRubric expects per-standard buckets) without adding a new
-- column to ``test_feedback_entry`` — the connection table already
-- exists and has no FK to a specific feedback table, so it works for
-- both attempt and test feedback rows.
--
-- The grade-creation flow is updated separately (see
-- ``core/app/tools/entries/test_feedback/create.py`` +
-- ``core/app/infra/test/feedback.py``) to populate the connection
-- when a new test feedback row is created. Existing rows have no
-- connection rows — their MV ``standard_id`` will be NULL and the
-- graded view will render them as "no per-standard breakdown
-- available" until they're re-graded.
--
-- 1:1 calling convention is preserved (one feedback row → one
-- standard_id), matching attempt. With that convention the
-- ``UNIQUE (feedback_id)`` MV index keeps holding under the LEFT
-- JOIN; no index change required.

DROP MATERIALIZED VIEW IF EXISTS public.test_feedback_mv CASCADE;

CREATE MATERIALIZED VIEW public.test_feedback_mv AS
 SELECT fe.id AS feedback_id,
    fe.grade_id,
    fe.call_id,
    fe.tool_call_id,
    fsc.standard_id,
    fe.total,
    fe.feedback,
    fe.total_points,
    fe.pass_points,
    fe.created_at
   FROM (public.test_feedback_entry fe
     LEFT JOIN public.feedbacks_standards_connection fsc ON ((fsc.feedbacks_id = fe.id)))
  WHERE (fe.active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_test_feedback_mv_feedback_id
    ON public.test_feedback_mv USING btree (feedback_id);

REFRESH MATERIALIZED VIEW public.test_feedback_mv;
