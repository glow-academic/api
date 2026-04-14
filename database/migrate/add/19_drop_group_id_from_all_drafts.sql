-- Migration: Remove group_id from all 19 draft tables
--
-- group_id is no longer stored on draft entries. Groups track their
-- associated drafts via the tool layer instead.
--
-- Steps:
--   1. Drop all 19 draft MVs
--   2. Drop all FKs and indexes on group_id
--   3. Drop group_id columns from all 19 tables
--   4. Recreate all 19 MVs without group_id

-- ============================================================================
-- Step 1: Drop all draft MVs
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS agent_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS auth_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS chat_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS cohort_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS department_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS document_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS eval_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS field_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS invocation_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS model_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS parameter_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS persona_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS profile_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS provider_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS rubric_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS scenario_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS setting_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS simulation_drafts_mv;
DROP MATERIALIZED VIEW IF EXISTS tool_drafts_mv;

-- ============================================================================
-- Step 2: Drop foreign keys
-- ============================================================================

ALTER TABLE public.agent_drafts_entry DROP CONSTRAINT IF EXISTS agent_drafts_entry_group_id_fkey;
ALTER TABLE public.auth_drafts_entry DROP CONSTRAINT IF EXISTS auth_drafts_entry_group_id_fkey;
ALTER TABLE public.chat_drafts_entry DROP CONSTRAINT IF EXISTS training_drafts_entry_group_id_fkey;
ALTER TABLE public.cohort_drafts_entry DROP CONSTRAINT IF EXISTS cohort_drafts_entry_group_id_fkey;
ALTER TABLE public.department_drafts_entry DROP CONSTRAINT IF EXISTS department_drafts_entry_group_id_fkey;
ALTER TABLE public.document_drafts_entry DROP CONSTRAINT IF EXISTS document_drafts_entry_group_id_fkey;
ALTER TABLE public.eval_drafts_entry DROP CONSTRAINT IF EXISTS eval_drafts_entry_group_id_fkey;
ALTER TABLE public.field_drafts_entry DROP CONSTRAINT IF EXISTS field_drafts_entry_group_id_fkey;
ALTER TABLE public.invocation_drafts_entry DROP CONSTRAINT IF EXISTS suite_drafts_entry_group_id_fkey;
ALTER TABLE public.model_drafts_entry DROP CONSTRAINT IF EXISTS model_drafts_entry_group_id_fkey;
ALTER TABLE public.parameter_drafts_entry DROP CONSTRAINT IF EXISTS parameter_drafts_entry_group_id_fkey;
ALTER TABLE public.persona_drafts_entry DROP CONSTRAINT IF EXISTS persona_drafts_entry_group_id_fkey;
ALTER TABLE public.profile_drafts_entry DROP CONSTRAINT IF EXISTS profile_drafts_entry_group_id_fkey;
ALTER TABLE public.provider_drafts_entry DROP CONSTRAINT IF EXISTS provider_drafts_entry_group_id_fkey;
ALTER TABLE public.rubric_drafts_entry DROP CONSTRAINT IF EXISTS rubric_drafts_entry_group_id_fkey;
ALTER TABLE public.scenario_drafts_entry DROP CONSTRAINT IF EXISTS scenario_drafts_entry_group_id_fkey;
ALTER TABLE public.setting_drafts_entry DROP CONSTRAINT IF EXISTS setting_drafts_entry_group_id_fkey;
ALTER TABLE public.simulation_drafts_entry DROP CONSTRAINT IF EXISTS simulation_drafts_entry_group_id_fkey;
ALTER TABLE public.tool_drafts_entry DROP CONSTRAINT IF EXISTS tool_drafts_entry_group_id_fkey;

-- ============================================================================
-- Step 3: Drop indexes
-- ============================================================================

DROP INDEX IF EXISTS idx_agent_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_auth_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_training_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_cohort_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_department_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_document_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_eval_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_field_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_suite_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_model_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_parameter_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_persona_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_profile_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_provider_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_rubric_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_scenario_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_setting_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_simulation_drafts_entry_group_id;
DROP INDEX IF EXISTS idx_tool_drafts_entry_group_id;

-- ============================================================================
-- Step 4: Drop columns
-- ============================================================================

ALTER TABLE public.agent_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.auth_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.chat_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.cohort_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.department_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.document_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.eval_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.field_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.invocation_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.model_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.parameter_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.persona_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.profile_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.provider_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.rubric_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.scenario_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.setting_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.simulation_drafts_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.tool_drafts_entry DROP COLUMN IF EXISTS group_id;

-- ============================================================================
-- Step 5: Recreate all 19 MVs without group_id
-- ============================================================================

CREATE MATERIALIZED VIEW public.agent_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.agent_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.auth_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.auth_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.chat_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.chat_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.cohort_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.cohort_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.department_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.department_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.document_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.document_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.eval_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.eval_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.field_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.field_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.invocation_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.invocation_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.model_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.model_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.parameter_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.parameter_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.persona_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.persona_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.profile_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.profile_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.provider_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.provider_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.rubric_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.rubric_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.scenario_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.scenario_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.setting_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.setting_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.simulation_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.simulation_drafts_entry WHERE (active = true) WITH NO DATA;

CREATE MATERIALIZED VIEW public.tool_drafts_mv AS
 SELECT id, created_at, generated, mcp, active, session_id
   FROM public.tool_drafts_entry WHERE (active = true) WITH NO DATA;
