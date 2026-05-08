-- v2.15.19_01_drafts_name_column.sql
--
-- Adds an immutable ``name`` column to every ``<artifact>_drafts_entry``
-- table. The column is set at draft-create time and never updated
-- thereafter (drafts have a stable identity — see PRD).
--
-- Three mechanical steps per artifact:
--   1. ADD COLUMN name TEXT NOT NULL DEFAULT '' (idempotent)
--   2. DROP + recreate the matching ``<artifact>_drafts_mv`` so the
--      column flows into the materialized view
--   3. Recreate the unique id index that the DROP removed, plus a
--      btree on ``lower(name)`` for upcoming searchable drafts work
--
-- Whole migration runs inside one transaction so a partial failure
-- never leaves the schema half-recreated. MVs are created WITH NO
-- DATA — runtime refresh fills them.

BEGIN;

-- ── agent ─────────────────────────────────────────────────────
ALTER TABLE public.agent_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.agent_drafts_mv;
CREATE MATERIALIZED VIEW public.agent_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.agent_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS agent_drafts_mv_id_idx
  ON public.agent_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS agent_drafts_mv_name_idx
  ON public.agent_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── auth ─────────────────────────────────────────────────────
ALTER TABLE public.auth_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.auth_drafts_mv;
CREATE MATERIALIZED VIEW public.auth_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.auth_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS auth_drafts_mv_id_idx
  ON public.auth_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS auth_drafts_mv_name_idx
  ON public.auth_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── chat ─────────────────────────────────────────────────────
ALTER TABLE public.chat_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.chat_drafts_mv;
CREATE MATERIALIZED VIEW public.chat_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.chat_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS chat_drafts_mv_id_idx
  ON public.chat_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS chat_drafts_mv_name_idx
  ON public.chat_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── cohort ─────────────────────────────────────────────────────
ALTER TABLE public.cohort_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.cohort_drafts_mv;
CREATE MATERIALIZED VIEW public.cohort_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.cohort_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS cohort_drafts_mv_id_idx
  ON public.cohort_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS cohort_drafts_mv_name_idx
  ON public.cohort_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── department ─────────────────────────────────────────────────────
ALTER TABLE public.department_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.department_drafts_mv;
CREATE MATERIALIZED VIEW public.department_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.department_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS department_drafts_mv_id_idx
  ON public.department_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS department_drafts_mv_name_idx
  ON public.department_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── document ─────────────────────────────────────────────────────
ALTER TABLE public.document_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.document_drafts_mv;
CREATE MATERIALIZED VIEW public.document_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.document_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS document_drafts_mv_id_idx
  ON public.document_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS document_drafts_mv_name_idx
  ON public.document_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── eval ─────────────────────────────────────────────────────
ALTER TABLE public.eval_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.eval_drafts_mv;
CREATE MATERIALIZED VIEW public.eval_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.eval_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS eval_drafts_mv_id_idx
  ON public.eval_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS eval_drafts_mv_name_idx
  ON public.eval_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── field ─────────────────────────────────────────────────────
ALTER TABLE public.field_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.field_drafts_mv;
CREATE MATERIALIZED VIEW public.field_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.field_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS field_drafts_mv_id_idx
  ON public.field_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS field_drafts_mv_name_idx
  ON public.field_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── invocation ─────────────────────────────────────────────────────
ALTER TABLE public.invocation_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.invocation_drafts_mv;
CREATE MATERIALIZED VIEW public.invocation_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.invocation_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS invocation_drafts_mv_id_idx
  ON public.invocation_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS invocation_drafts_mv_name_idx
  ON public.invocation_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── model ─────────────────────────────────────────────────────
ALTER TABLE public.model_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.model_drafts_mv;
CREATE MATERIALIZED VIEW public.model_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.model_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS model_drafts_mv_id_idx
  ON public.model_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS model_drafts_mv_name_idx
  ON public.model_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── parameter ─────────────────────────────────────────────────────
ALTER TABLE public.parameter_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.parameter_drafts_mv;
CREATE MATERIALIZED VIEW public.parameter_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.parameter_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS parameter_drafts_mv_id_idx
  ON public.parameter_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS parameter_drafts_mv_name_idx
  ON public.parameter_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── persona ─────────────────────────────────────────────────────
ALTER TABLE public.persona_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.persona_drafts_mv;
CREATE MATERIALIZED VIEW public.persona_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.persona_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS persona_drafts_mv_id_idx
  ON public.persona_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS persona_drafts_mv_name_idx
  ON public.persona_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── profile ─────────────────────────────────────────────────────
ALTER TABLE public.profile_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.profile_drafts_mv;
CREATE MATERIALIZED VIEW public.profile_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.profile_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS profile_drafts_mv_id_idx
  ON public.profile_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS profile_drafts_mv_name_idx
  ON public.profile_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── provider ─────────────────────────────────────────────────────
ALTER TABLE public.provider_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.provider_drafts_mv;
CREATE MATERIALIZED VIEW public.provider_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.provider_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS provider_drafts_mv_id_idx
  ON public.provider_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS provider_drafts_mv_name_idx
  ON public.provider_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── rubric ─────────────────────────────────────────────────────
ALTER TABLE public.rubric_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.rubric_drafts_mv;
CREATE MATERIALIZED VIEW public.rubric_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.rubric_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS rubric_drafts_mv_id_idx
  ON public.rubric_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS rubric_drafts_mv_name_idx
  ON public.rubric_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── scenario ─────────────────────────────────────────────────────
ALTER TABLE public.scenario_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.scenario_drafts_mv;
CREATE MATERIALIZED VIEW public.scenario_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.scenario_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS scenario_drafts_mv_id_idx
  ON public.scenario_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS scenario_drafts_mv_name_idx
  ON public.scenario_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── setting ─────────────────────────────────────────────────────
ALTER TABLE public.setting_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.setting_drafts_mv;
CREATE MATERIALIZED VIEW public.setting_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.setting_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS setting_drafts_mv_id_idx
  ON public.setting_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS setting_drafts_mv_name_idx
  ON public.setting_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── simulation ─────────────────────────────────────────────────────
ALTER TABLE public.simulation_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.simulation_drafts_mv;
CREATE MATERIALIZED VIEW public.simulation_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.simulation_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS simulation_drafts_mv_id_idx
  ON public.simulation_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS simulation_drafts_mv_name_idx
  ON public.simulation_drafts_mv USING btree (lower(name) text_pattern_ops);

-- ── tool ─────────────────────────────────────────────────────
ALTER TABLE public.tool_drafts_entry
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';

DROP MATERIALIZED VIEW IF EXISTS public.tool_drafts_mv;
CREATE MATERIALIZED VIEW public.tool_drafts_mv AS
  SELECT id, created_at, generated, mcp, active, session_id, name
    FROM public.tool_drafts_entry
   WHERE active = true
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS tool_drafts_mv_id_idx
  ON public.tool_drafts_mv USING btree (id);
CREATE INDEX IF NOT EXISTS tool_drafts_mv_name_idx
  ON public.tool_drafts_mv USING btree (lower(name) text_pattern_ops);

COMMIT;
