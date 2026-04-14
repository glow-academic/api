-- Migration: Add missing unique indexes to all draft MVs.
-- Required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
-- These were lost when migration 19 rebuilt the MVs without recreating indexes.

CREATE UNIQUE INDEX IF NOT EXISTS agent_drafts_mv_id_idx ON public.agent_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS auth_drafts_mv_id_idx ON public.auth_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS chat_drafts_mv_id_idx ON public.chat_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS cohort_drafts_mv_id_idx ON public.cohort_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS department_drafts_mv_id_idx ON public.department_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS document_drafts_mv_id_idx ON public.document_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS eval_drafts_mv_id_idx ON public.eval_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS field_drafts_mv_id_idx ON public.field_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS invocation_drafts_mv_id_idx ON public.invocation_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS model_drafts_mv_id_idx ON public.model_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS parameter_drafts_mv_id_idx ON public.parameter_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS persona_drafts_mv_id_idx ON public.persona_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS profile_drafts_mv_id_idx ON public.profile_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS provider_drafts_mv_id_idx ON public.provider_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS rubric_drafts_mv_id_idx ON public.rubric_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS scenario_drafts_mv_id_idx ON public.scenario_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS setting_drafts_mv_id_idx ON public.setting_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS simulation_drafts_mv_id_idx ON public.simulation_drafts_mv USING btree (id);
CREATE UNIQUE INDEX IF NOT EXISTS tool_drafts_mv_id_idx ON public.tool_drafts_mv USING btree (id);
