-- Migration: Remove redundant run_id columns and profiles_runs_connection
--
-- These columns are derivable via call_id → calls_entry.run_id.
-- profiles_runs_connection is replaced by profiles_sessions_connection in runs_mv.
--
-- Steps:
--   1. Drop dependent MVs (attempt_conversations_mv, test_grade_mv, runs_mv)
--   2. Drop FKs and indexes on run_id columns
--   3. Drop run_id columns from attempt_grade_entry, attempt_conversations_entry, test_grade_entry
--   4. Drop profiles_runs_connection table (FKs cascade)
--   5. Recreate MVs without run_id / with profiles_sessions_connection

-- ============================================================================
-- Step 1: Drop dependent materialized views
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS attempt_conversations_mv;
DROP MATERIALIZED VIEW IF EXISTS test_grade_mv;
DROP MATERIALIZED VIEW IF EXISTS runs_mv;

-- ============================================================================
-- Step 2: Drop foreign keys on run_id
-- ============================================================================

ALTER TABLE public.attempt_grade_entry
    DROP CONSTRAINT IF EXISTS attempt_grade_entry_run_id_fkey;

ALTER TABLE public.attempt_conversations_entry
    DROP CONSTRAINT IF EXISTS attempt_conversations_entry_run_id_fkey;

ALTER TABLE public.test_grade_entry
    DROP CONSTRAINT IF EXISTS benchmark_grades_entry_run_id_fkey;

-- ============================================================================
-- Step 3: Drop indexes on run_id
-- ============================================================================

DROP INDEX IF EXISTS idx_simulation_grades_run_id;
DROP INDEX IF EXISTS idx_attempt_conversations_entry_run_id;
DROP INDEX IF EXISTS idx_benchmark_grades_run_id;

-- ============================================================================
-- Step 4: Drop run_id columns
-- ============================================================================

ALTER TABLE public.attempt_grade_entry DROP COLUMN IF EXISTS run_id;
ALTER TABLE public.attempt_conversations_entry DROP COLUMN IF EXISTS run_id;
ALTER TABLE public.test_grade_entry DROP COLUMN IF EXISTS run_id;

-- ============================================================================
-- Step 5: Drop profiles_runs_connection table
-- ============================================================================

DROP TABLE IF EXISTS public.profiles_runs_connection CASCADE;

-- ============================================================================
-- Step 6: Recreate attempt_conversations_mv (without run_id)
-- ============================================================================

CREATE MATERIALIZED VIEW public.attempt_conversations_mv AS
 SELECT id,
    created_at,
    generated,
    mcp,
    active,
    chat_id,
    call_id
   FROM public.attempt_conversations_entry
  WHERE (active = true)
  WITH NO DATA;

-- ============================================================================
-- Step 7: Recreate test_grade_mv (without run_id)
-- ============================================================================

CREATE MATERIALIZED VIEW public.test_grade_mv AS
 SELECT id,
    invocation_id,
    created_at,
    updated_at,
    passed,
    score,
    time_taken,
    generated,
    mcp,
    active,
    call_id
   FROM public.test_grade_entry
  WHERE (active = true)
  WITH NO DATA;

-- ============================================================================
-- Step 8: Recreate runs_mv (profiles_sessions_connection instead of profiles_runs_connection)
-- ============================================================================

CREATE MATERIALIZED VIEW public.runs_mv AS
 WITH agents_agg AS (
         SELECT rac.run_id,
            COALESCE(array_agg(DISTINCT rac.agents_id) FILTER (WHERE (rac.agents_id IS NOT NULL)), ARRAY[]::uuid[]) AS agent_ids,
            COALESCE(array_agg(DISTINCT ar.model_id) FILTER (WHERE (ar.model_id IS NOT NULL)), ARRAY[]::uuid[]) AS model_ids,
            COALESCE(array_agg(DISTINCT mr.provider_id) FILTER (WHERE (mr.provider_id IS NOT NULL)), ARRAY[]::uuid[]) AS provider_ids
           FROM ((public.runs_agents_connection rac
             JOIN public.agents_resource ar ON (((ar.id = rac.agents_id) AND (ar.active = true))))
             LEFT JOIN public.models_resource mr ON ((mr.id = ar.model_id)))
          WHERE (rac.active = true)
          GROUP BY rac.run_id
        ), pricing_input AS (
         SELECT rpe.run_id,
            rpe.count AS pricing_count,
            rppc.pricing_id
           FROM (public.run_pricing_entry rpe
             JOIN public.run_pricing_pricing_connection rppc ON (((rppc.run_pricing_id = rpe.id) AND (rppc.active = true))))
          WHERE ((rpe.active = true) AND (rpe.pricing_type = 'input'::public.pricing_type))
        ), pricing_output AS (
         SELECT rpe.run_id,
            rpe.count AS pricing_count,
            rppc.pricing_id
           FROM (public.run_pricing_entry rpe
             JOIN public.run_pricing_pricing_connection rppc ON (((rppc.run_pricing_id = rpe.id) AND (rppc.active = true))))
          WHERE ((rpe.active = true) AND (rpe.pricing_type = 'output'::public.pricing_type))
        ), pricing_cached AS (
         SELECT rpe.run_id,
            rpe.count AS pricing_count,
            rppc.pricing_id
           FROM (public.run_pricing_entry rpe
             JOIN public.run_pricing_pricing_connection rppc ON (((rppc.run_pricing_id = rpe.id) AND (rppc.active = true))))
          WHERE ((rpe.active = true) AND (rpe.pricing_type = 'cached'::public.pricing_type))
        )
 SELECT r.id AS run_id,
    r.group_id,
    COALESCE(te.input_tokens, 0) AS input_tokens,
    COALESCE(te.output_tokens, 0) AS output_tokens,
    COALESCE(te.cached_input_tokens, 0) AS cached_input_tokens,
    r.created_at AS run_created_at,
    COALESCE(ca.agent_ids, ARRAY[]::uuid[]) AS agent_ids,
    COALESCE(ca.model_ids, ARRAY[]::uuid[]) AS model_ids,
    COALESCE(ca.provider_ids, ARRAY[]::uuid[]) AS provider_ids,
    pi.pricing_count AS input_pricing_count,
    pi.pricing_id AS input_pricing_pricing_id,
    po.pricing_count AS output_pricing_count,
    po.pricing_id AS output_pricing_pricing_id,
    pc.pricing_count AS cached_pricing_count,
    pc.pricing_id AS cached_pricing_pricing_id,
    psc.profiles_id
   FROM ((((((public.runs_entry r
     LEFT JOIN LATERAL ( SELECT tokens_entry.input_tokens,
            tokens_entry.output_tokens,
            tokens_entry.cached_input_tokens
           FROM public.tokens_entry
          WHERE ((tokens_entry.run_id = r.id) AND (tokens_entry.active = true))
          ORDER BY tokens_entry.created_at DESC
         LIMIT 1) te ON (true))
     LEFT JOIN agents_agg ca ON ((ca.run_id = r.id)))
     LEFT JOIN pricing_input pi ON ((pi.run_id = r.id)))
     LEFT JOIN pricing_output po ON ((po.run_id = r.id)))
     LEFT JOIN pricing_cached pc ON ((pc.run_id = r.id)))
     LEFT JOIN public.profiles_sessions_connection psc ON (((psc.session_id = r.session_id) AND (psc.active = true))))
  WHERE (r.group_id IS NOT NULL)
  WITH NO DATA;
