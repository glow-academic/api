-- Migration: Add call_id and tool_call_id to test_feedback_mv
-- Purpose: Expose which call produced the feedback and which tool call is being evaluated

DROP MATERIALIZED VIEW IF EXISTS public.test_feedback_mv;

CREATE MATERIALIZED VIEW public.test_feedback_mv AS
SELECT id AS feedback_id,
    grade_id,
    call_id,
    tool_call_id,
    total,
    feedback,
    total_points,
    pass_points,
    created_at
   FROM public.test_feedback_entry fe
  WHERE (active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX idx_test_feedback_mv_feedback_id ON public.test_feedback_mv USING btree (feedback_id);
