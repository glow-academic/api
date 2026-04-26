-- v2.15.18_04_test_invocation_mvs_recreate.sql
--
-- Recreate the materialized views that migration 01 dropped (CASCADE)
-- with shapes that match the new schema:
--
--   - test_invocation_traces_completion_mv  (renamed from groups_completion_mv,
--                                            FK column renamed)
--   - test_invocation_traces_mv              (renamed from groups_mv,
--                                            no agents agg, has run_id)
--   - test_invocation_runs_completion_mv     (no schema change, just recreate)
--   - test_invocation_runs_mv                (simplified — no connection-
--                                            table aggs, has run_id +
--                                            test_invocation_traces_id)
--   - test_invocation_mv                     (rebuilt CTEs without
--                                            groups_agents_links and
--                                            runs_agents_links — agents
--                                            come from invocation only)
--
-- All views WITH NO DATA — runtime refresh fills them.

-- ──────────────────────────────────────────────────────────────────────
-- 1. Trace completion MV (renamed)
-- ──────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS public.test_invocation_traces_completion_mv AS
 SELECT id,
    test_invocation_traces_id,
    stop,
    error,
    message,
    call_id,
    created_at,
    active,
    generated,
    mcp
   FROM public.test_invocation_traces_completion_entry
  WHERE (active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_test_invocation_traces_completion_mv_id
  ON public.test_invocation_traces_completion_mv USING btree (id);

-- ──────────────────────────────────────────────────────────────────────
-- 2. Traces MV (renamed; no agents column; new run_id)
-- ──────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS public.test_invocation_traces_mv AS
 SELECT e.id,
    e.test_invocation_id,
    e.run_id,
    e.created_at,
    e.updated_at,
    e.generated,
    e.mcp,
    e.active,
    COALESCE(array_agg(DISTINCT rlc.reasoning_levels_id) FILTER (WHERE (rlc.reasoning_levels_id IS NOT NULL)), ARRAY[]::uuid[]) AS reasoning_level_ids,
    COALESCE(array_agg(DISTINCT tlc.temperature_levels_id) FILTER (WHERE (tlc.temperature_levels_id IS NOT NULL)), ARRAY[]::uuid[]) AS temperature_level_ids,
    COALESCE(array_agg(DISTINCT vc.voices_id) FILTER (WHERE (vc.voices_id IS NOT NULL)), ARRAY[]::uuid[]) AS voice_ids,
    COALESCE(array_agg(DISTINCT pc.prompts_id) FILTER (WHERE (pc.prompts_id IS NOT NULL)), ARRAY[]::uuid[]) AS prompt_ids,
    COALESCE(array_agg(DISTINCT ic.instructions_id) FILTER (WHERE (ic.instructions_id IS NOT NULL)), ARRAY[]::uuid[]) AS instruction_ids,
    COALESCE(array_agg(DISTINCT tc.tools_id) FILTER (WHERE (tc.tools_id IS NOT NULL)), ARRAY[]::uuid[]) AS tool_ids,
    COALESCE(array_agg(DISTINCT qc.qualities_id) FILTER (WHERE (qc.qualities_id IS NOT NULL)), ARRAY[]::uuid[]) AS quality_ids,
    COALESCE(array_agg(DISTINCT mc.modalities_id) FILTER (WHERE (mc.modalities_id IS NOT NULL)), ARRAY[]::uuid[]) AS modality_ids
   FROM ((((((((public.test_invocation_traces_entry e
     LEFT JOIN public.test_invocation_traces_reasoning_levels_connection rlc ON (((rlc.test_invocation_traces_id = e.id) AND (rlc.active = true))))
     LEFT JOIN public.test_invocation_traces_temperature_levels_connection tlc ON (((tlc.test_invocation_traces_id = e.id) AND (tlc.active = true))))
     LEFT JOIN public.test_invocation_traces_voices_connection vc ON (((vc.test_invocation_traces_id = e.id) AND (vc.active = true))))
     LEFT JOIN public.test_invocation_traces_prompts_connection pc ON (((pc.test_invocation_traces_id = e.id) AND (pc.active = true))))
     LEFT JOIN public.test_invocation_traces_instructions_connection ic ON (((ic.test_invocation_traces_id = e.id) AND (ic.active = true))))
     LEFT JOIN public.test_invocation_traces_tools_connection tc ON (((tc.test_invocation_traces_id = e.id) AND (tc.active = true))))
     LEFT JOIN public.test_invocation_traces_qualities_connection qc ON (((qc.test_invocation_traces_id = e.id) AND (qc.active = true))))
     LEFT JOIN public.test_invocation_traces_modalities_connection mc ON (((mc.test_invocation_traces_id = e.id) AND (mc.active = true))))
  WHERE (e.active = true)
  GROUP BY e.id, e.test_invocation_id, e.run_id, e.created_at, e.updated_at, e.generated, e.mcp, e.active
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_test_invocation_traces_mv_id
  ON public.test_invocation_traces_mv USING btree (id);

-- ──────────────────────────────────────────────────────────────────────
-- 3. Runs completion MV (recreate, schema unchanged)
-- ──────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS public.test_invocation_runs_completion_mv AS
 SELECT id,
    test_invocation_runs_id,
    stop,
    error,
    message,
    call_id,
    created_at,
    active,
    generated,
    mcp
   FROM public.test_invocation_runs_completion_entry
  WHERE (active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_test_invocation_runs_completion_mv_id
  ON public.test_invocation_runs_completion_mv USING btree (id);

-- ──────────────────────────────────────────────────────────────────────
-- 4. Runs MV (simplified — runs are pure binding rows now)
-- ──────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS public.test_invocation_runs_mv AS
 SELECT e.id,
    e.test_invocation_id,
    e.test_invocation_traces_id,
    e.run_id,
    e.created_at,
    e.updated_at,
    e.generated,
    e.mcp,
    e.active
   FROM public.test_invocation_runs_entry e
  WHERE (e.active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_test_invocation_runs_mv_id
  ON public.test_invocation_runs_mv USING btree (id);

-- ──────────────────────────────────────────────────────────────────────
-- 5. test_invocation_mv (parent — drop the agent-aggregation CTEs that
--    referenced the removed connection tables; agent_ids comes from
--    invocation level only).
-- ──────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS public.test_invocation_mv AS
 WITH department_links AS (
         SELECT dc.test_invocation_id,
            array_agg(DISTINCT dc.departments_id) FILTER (WHERE (dc.departments_id IS NOT NULL)) AS department_ids
           FROM public.test_invocation_departments_connection dc
          WHERE (dc.active = true)
          GROUP BY dc.test_invocation_id
        ), latest_grade AS (
         SELECT DISTINCT ON (g.invocation_id) g.id AS grade_id,
            g.invocation_id,
            g.score AS grade_score,
            g.passed AS grade_passed,
            g.time_taken AS grade_time_taken
           FROM public.test_grade_entry g
          WHERE (g.active = true)
          ORDER BY g.invocation_id, g.created_at DESC
        ), latest_completion AS (
         SELECT DISTINCT ON (c.invocation_id) c.id AS completion_id,
            c.invocation_id
           FROM public.test_invocation_completion_entry c
          WHERE (c.active = true)
          ORDER BY c.invocation_id, c.created_at DESC
        ), bundle_snapshot AS (
         SELECT ir.id AS test_invocation_id,
            COALESCE(array_agg(DISTINCT ira.agents_id ORDER BY ira.agents_id) FILTER (WHERE (ira.agents_id IS NOT NULL)), ARRAY[]::uuid[]) AS agent_ids,
            (array_agg(irr.rubrics_id) FILTER (WHERE (irr.rubrics_id IS NOT NULL)))[1] AS rubric_id,
            (array_agg(irq.qualities_id) FILTER (WHERE (irq.qualities_id IS NOT NULL)))[1] AS quality_id,
            (array_agg(irv.voices_id) FILTER (WHERE (irv.voices_id IS NOT NULL)))[1] AS voice_id,
            (array_agg(irt.temperature_levels_id) FILTER (WHERE (irt.temperature_levels_id IS NOT NULL)))[1] AS temperature_level_id,
            (array_agg(irrl.reasoning_levels_id) FILTER (WHERE (irrl.reasoning_levels_id IS NOT NULL)))[1] AS reasoning_level_id,
            COALESCE(array_agg(DISTINCT irmod.modalities_id ORDER BY irmod.modalities_id) FILTER (WHERE (irmod.modalities_id IS NOT NULL)), ARRAY[]::uuid[]) AS modality_ids
           FROM (((((((public.test_invocation_entry ir
             LEFT JOIN public.test_invocation_agents_connection ira ON (((ira.test_invocation_id = ir.id) AND (ira.active = true))))
             LEFT JOIN public.test_invocation_rubrics_connection irr ON (((irr.test_invocation_id = ir.id) AND (irr.active = true))))
             LEFT JOIN public.test_invocation_qualities_connection irq ON (((irq.test_invocation_id = ir.id) AND (irq.active = true))))
             LEFT JOIN public.test_invocation_voices_connection irv ON (((irv.test_invocation_id = ir.id) AND (irv.active = true))))
             LEFT JOIN public.test_invocation_temperature_levels_connection irt ON (((irt.test_invocation_id = ir.id) AND (irt.active = true))))
             LEFT JOIN public.test_invocation_reasoning_levels_connection irrl ON (((irrl.test_invocation_id = ir.id) AND (irrl.active = true))))
             LEFT JOIN public.test_invocation_modalities_connection irmod ON (((irmod.test_invocation_id = ir.id) AND (irmod.active = true))))
          WHERE (ir.active = true)
          GROUP BY ir.id
        )
 SELECT i.id AS invocation_id,
    i.test_id,
    r_grp.group_id,
    i.created_at AS invocation_created_at,
    i.title AS invocation_title,
    i.use_custom,
    i."position",
    ((lg.invocation_id IS NOT NULL) OR (lc.invocation_id IS NOT NULL)) AS invocation_completed,
    lg.grade_id,
    lg.grade_score,
    lg.grade_passed,
    lg.grade_time_taken,
    bs.rubric_id,
    COALESCE(bs.agent_ids, ARRAY[]::uuid[]) AS agent_ids,
    bs.quality_id,
    COALESCE(dl.department_ids, ARRAY[]::uuid[]) AS department_ids,
    bs.voice_id,
    bs.temperature_level_id,
    bs.reasoning_level_id,
    COALESCE(bs.modality_ids, ARRAY[]::uuid[]) AS modality_ids
   FROM ((((((public.test_invocation_entry i
     LEFT JOIN public.calls_entry cl_grp ON ((cl_grp.id = i.call_id)))
     LEFT JOIN public.runs_entry r_grp ON ((r_grp.id = cl_grp.run_id)))
     LEFT JOIN department_links dl ON ((dl.test_invocation_id = i.id)))
     LEFT JOIN latest_grade lg ON ((lg.invocation_id = i.id)))
     LEFT JOIN latest_completion lc ON ((lc.invocation_id = i.id)))
     LEFT JOIN bundle_snapshot bs ON ((bs.test_invocation_id = i.id)))
  WHERE (i.active = true)
  WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS test_invocation_mv_invocation_id_idx
  ON public.test_invocation_mv USING btree (invocation_id);
