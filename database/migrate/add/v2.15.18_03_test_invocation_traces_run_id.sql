-- v2.15.18_03_test_invocation_traces_run_id.sql
--
-- Add the historical run_id binding on test_invocation_traces_entry.
--
-- Semantics:
--   - Manual replay: the original benchmark run we're replaying against.
--     Conversation prefill reads messages from this run.
--   - Online eval: the live run that just executed; the trace and the
--     run binding both point to the same run_id (no replay — we're
--     attaching for grading).
--
-- Idempotent.

ALTER TABLE public.test_invocation_traces_entry
    ADD COLUMN IF NOT EXISTS run_id uuid REFERENCES public.runs_entry(id);

CREATE INDEX IF NOT EXISTS idx_test_invocation_traces_entry_run_id
    ON public.test_invocation_traces_entry(run_id);
