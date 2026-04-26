-- v2.15.18_02_test_invocation_runs_link.sql
--
-- Simplify test_invocation_runs_entry to a binding/tracking row.
-- All bundle config (instructions/prompts/tools/modalities/voices/temp/
-- reasoning/qualities + agents) moves up to the trace level. Add direct
-- FKs from runs → runs_entry (the row holding the model output) and
-- runs → traces (the parent trace this run belongs to).
--
-- Idempotent: DROP TABLE IF EXISTS, ADD COLUMN IF NOT EXISTS, etc.

-- ──────────────────────────────────────────────────────────────────────
-- 1. Drop all 9 _runs_*_connection tables. Bundle config now lives on
--    test_invocation_traces_*_connection. Both manual replay and online
--    eval write to the trace side from now on.
-- ──────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS public.test_invocation_runs_agents_connection;
DROP TABLE IF EXISTS public.test_invocation_runs_instructions_connection;
DROP TABLE IF EXISTS public.test_invocation_runs_modalities_connection;
DROP TABLE IF EXISTS public.test_invocation_runs_prompts_connection;
DROP TABLE IF EXISTS public.test_invocation_runs_qualities_connection;
DROP TABLE IF EXISTS public.test_invocation_runs_reasoning_levels_connection;
DROP TABLE IF EXISTS public.test_invocation_runs_temperature_levels_connection;
DROP TABLE IF EXISTS public.test_invocation_runs_tools_connection;
DROP TABLE IF EXISTS public.test_invocation_runs_voices_connection;

-- ──────────────────────────────────────────────────────────────────────
-- 2. Direct FK to the runs_entry row this binding tracks. Set when the
--    client (or setup_generation_test) creates the test_invocation_runs
--    row after a generate call.
-- ──────────────────────────────────────────────────────────────────────
ALTER TABLE public.test_invocation_runs_entry
    ADD COLUMN IF NOT EXISTS run_id uuid REFERENCES public.runs_entry(id);

CREATE INDEX IF NOT EXISTS idx_test_invocation_runs_entry_run_id
    ON public.test_invocation_runs_entry(run_id);

-- ──────────────────────────────────────────────────────────────────────
-- 3. Parent-trace FK. Every run binding belongs to exactly one trace.
--    Nullable for now to allow pre-migration rows; flip to NOT NULL
--    after a backfill pass once both flows populate it.
--    ON DELETE CASCADE matches the trace ↔ run lifetime semantics.
-- ──────────────────────────────────────────────────────────────────────
ALTER TABLE public.test_invocation_runs_entry
    ADD COLUMN IF NOT EXISTS test_invocation_traces_id uuid
        REFERENCES public.test_invocation_traces_entry(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_test_invocation_runs_entry_traces_id
    ON public.test_invocation_runs_entry(test_invocation_traces_id);
