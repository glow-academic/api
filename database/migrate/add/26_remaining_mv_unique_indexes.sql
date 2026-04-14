-- Migration: Add missing unique indexes to remaining MVs.
-- Required for REFRESH MATERIALIZED VIEW CONCURRENTLY.

CREATE UNIQUE INDEX IF NOT EXISTS attempt_chat_mv_chat_id_idx ON public.attempt_chat_mv USING btree (chat_id);
CREATE UNIQUE INDEX IF NOT EXISTS attempt_conversations_mv_id_idx ON public.attempt_conversations_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS runs_mv_run_id_idx ON public.runs_mv USING btree (run_id);
CREATE UNIQUE INDEX IF NOT EXISTS test_grade_mv_id_idx ON public.test_grade_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS test_invocation_mv_invocation_id_idx ON public.test_invocation_mv USING btree (invocation_id);
