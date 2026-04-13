-- Migration: Remove group_id from attempt_chat_entry and test_invocation_entry
--
-- group_id is now derived in the MVs via call_id → calls_entry → runs_entry.group_id.
-- Consumers see no change — MVs still expose group_id as a column.
--
-- Steps:
--   1. Drop dependent MVs
--   2. Drop FKs and indexes on group_id
--   3. Drop group_id columns
--   4. Recreate MVs with derived group_id

-- ============================================================================
-- Step 1: Drop dependent materialized views
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS attempt_chat_mv;
DROP MATERIALIZED VIEW IF EXISTS test_invocation_mv;

-- ============================================================================
-- Step 2: Drop foreign keys
-- ============================================================================

ALTER TABLE public.attempt_chat_entry
    DROP CONSTRAINT IF EXISTS attempt_chat_entry_group_id_fkey;

ALTER TABLE public.test_invocation_entry
    DROP CONSTRAINT IF EXISTS benchmark_chats_entry_group_id_fkey;

-- ============================================================================
-- Step 3: Drop indexes
-- ============================================================================

DROP INDEX IF EXISTS idx_attempt_chat_entry_group_id;
DROP INDEX IF EXISTS idx_benchmark_invocations_entry_group_id;
DROP INDEX IF EXISTS ux_benchmark_invocations_active_group_id;

-- ============================================================================
-- Step 4: Drop columns
-- ============================================================================

ALTER TABLE public.attempt_chat_entry DROP COLUMN IF EXISTS group_id;
ALTER TABLE public.test_invocation_entry DROP COLUMN IF EXISTS group_id;

-- ============================================================================
-- Step 5: Recreate attempt_chat_mv (group_id derived via call → run)
-- ============================================================================

CREATE MATERIALIZED VIEW public.attempt_chat_mv AS
 WITH latest_grade AS (
         SELECT DISTINCT ON (g.chat_id) g.id AS grade_id,
            g.chat_id,
            g.score AS grade_score,
            g.passed AS grade_passed,
            g.time_taken AS grade_time_taken
           FROM public.attempt_grade_entry g
          WHERE (g.active = true)
          ORDER BY g.chat_id, g.created_at DESC
        ), chat_rubric AS (
         SELECT DISTINCT ON (acrc.attempt_chat_id) acrc.attempt_chat_id,
            acrc.rubrics_id AS rubric_id,
            r.total_points AS rubric_total_points,
            r.pass_points AS rubric_pass_points
           FROM (public.attempt_chat_rubrics_connection acrc
             JOIN public.rubrics_resource r ON ((r.id = acrc.rubrics_id)))
          WHERE (acrc.active = true)
          ORDER BY acrc.attempt_chat_id, acrc.created_at DESC
        ), chat_scope AS (
         SELECT c_1.id AS chat_id,
            (array_agg(csc.scenarios_id ORDER BY csc.created_at) FILTER (WHERE (csc.scenarios_id IS NOT NULL)))[1] AS scenario_id
           FROM (public.attempt_chat_entry c_1
             LEFT JOIN public.chat_scenarios_connection csc ON (((csc.chat_id = c_1.chat_id) AND (csc.active = true))))
          WHERE (c_1.active = true)
          GROUP BY c_1.id
        ), chat_personas AS (
         SELECT c_1.id AS chat_id,
            array_agg(DISTINCT ppc.personas_id) FILTER (WHERE (ppc.personas_id IS NOT NULL)) AS persona_ids
           FROM ((public.attempt_chat_entry c_1
             LEFT JOIN LATERAL unnest(c_1.assistant_persona_ids) pe_id(pe_id) ON (true))
             LEFT JOIN public.personas_personas_connection ppc ON (((ppc.personas_entry_id = pe_id.pe_id) AND (ppc.active = true))))
          WHERE (c_1.active = true)
          GROUP BY c_1.id
        ), chat_documents AS (
         SELECT acdc.attempt_chat_id AS chat_id,
            array_agg(DISTINCT acdc.documents_id) FILTER (WHERE (acdc.documents_id IS NOT NULL)) AS document_ids
           FROM public.attempt_chat_documents_connection acdc
          WHERE (acdc.active = true)
          GROUP BY acdc.attempt_chat_id
        ), chat_problem_statements AS (
         SELECT DISTINCT ON (acpsc.attempt_chat_id) acpsc.attempt_chat_id AS chat_id,
            acpsc.problem_statements_id AS problem_statement_id
           FROM public.attempt_chat_problem_statements_connection acpsc
          WHERE (acpsc.active = true)
          ORDER BY acpsc.attempt_chat_id, acpsc.created_at DESC
        ), chat_objectives AS (
         SELECT acoc.attempt_chat_id AS chat_id,
            array_agg(DISTINCT acoc.objectives_id) FILTER (WHERE (acoc.objectives_id IS NOT NULL)) AS objective_ids
           FROM public.attempt_chat_objectives_connection acoc
          WHERE (acoc.active = true)
          GROUP BY acoc.attempt_chat_id
        ), chat_questions AS (
         SELECT acqc.attempt_chat_id AS chat_id,
            array_agg(DISTINCT acqc.questions_id) FILTER (WHERE (acqc.questions_id IS NOT NULL)) AS question_ids
           FROM public.attempt_chat_questions_connection acqc
          WHERE (acqc.active = true)
          GROUP BY acqc.attempt_chat_id
        ), chat_options AS (
         SELECT acoptc.attempt_chat_id AS chat_id,
            array_agg(DISTINCT acoptc.options_id) FILTER (WHERE (acoptc.options_id IS NOT NULL)) AS option_ids
           FROM public.attempt_chat_options_connection acoptc
          WHERE (acoptc.active = true)
          GROUP BY acoptc.attempt_chat_id
        ), chat_images AS (
         SELECT acic.attempt_chat_id AS chat_id,
            array_agg(DISTINCT acic.images_id) FILTER (WHERE (acic.images_id IS NOT NULL)) AS image_ids
           FROM public.attempt_chat_images_connection acic
          WHERE (acic.active = true)
          GROUP BY acic.attempt_chat_id
        ), chat_videos AS (
         SELECT acvc.attempt_chat_id AS chat_id,
            array_agg(DISTINCT acvc.videos_id) FILTER (WHERE (acvc.videos_id IS NOT NULL)) AS video_ids
           FROM public.attempt_chat_videos_connection acvc
          WHERE (acvc.active = true)
          GROUP BY acvc.attempt_chat_id
        ), chat_standard_groups AS (
         SELECT acsgc.attempt_chat_id AS chat_id,
            array_agg(DISTINCT acsgc.standard_groups_id) FILTER (WHERE (acsgc.standard_groups_id IS NOT NULL)) AS standard_group_ids
           FROM public.attempt_chat_standard_groups_connection acsgc
          WHERE (acsgc.active = true)
          GROUP BY acsgc.attempt_chat_id
        ), chat_standards AS (
         SELECT acsc.attempt_chat_id AS chat_id,
            array_agg(DISTINCT acsc.standards_id) FILTER (WHERE (acsc.standards_id IS NOT NULL)) AS standard_ids
           FROM public.attempt_chat_standards_connection acsc
          WHERE (acsc.active = true)
          GROUP BY acsc.attempt_chat_id
        ), chat_time_limits AS (
         SELECT DISTINCT ON (cstlc.chat_id) cstlc.chat_id,
            stlr.time_limit_seconds,
            stlr.negative
           FROM (public.chat_scenario_time_limits_connection cstlc
             JOIN public.scenario_time_limits_resource stlr ON ((stlr.id = cstlc.scenario_time_limits_id)))
          WHERE ((cstlc.active = true) AND (stlr.active = true))
          ORDER BY cstlc.chat_id, cstlc.created_at DESC
        )
 SELECT c.id AS chat_id,
    ac.attempt_id,
    c.chat_id AS chat_entry_id,
    r_grp.group_id,
    apc.profiles_id AS profile_id,
    COALESCE(home_coh.cohorts_id, prac_coh.cohorts_id) AS cohort_id,
    COALESCE(home_dep.departments_id, prac_dep.departments_id) AS department_id,
    COALESCE(home_sim.simulations_id, prac_sim.simulations_id) AS simulation_id,
    cs.scenario_id,
    cp.persona_ids,
    cr.rubric_id,
    lg.grade_score,
    cr.rubric_total_points AS grade_total_points,
    cr.rubric_pass_points AS grade_pass_points,
    lg.grade_passed,
    lg.grade_time_taken,
    (EXISTS ( SELECT 1
           FROM public.attempt_chat_completion_entry comp
          WHERE ((comp.chat_id = c.id) AND (comp.active = true)))) AS completed,
    (dense_rank() OVER (PARTITION BY apc.profiles_id, COALESCE(home_sim.simulations_id, prac_sim.simulations_id) ORDER BY a.created_at, ac.attempt_id))::integer AS attempt_number,
    c.created_at AS chat_created_at,
    ((a.created_at AT TIME ZONE 'UTC'::text))::date AS attempt_date,
        CASE
            WHEN (ape.attempt_id IS NOT NULL) THEN 'practice'::text
            ELSE 'general'::text
        END AS attempt_type,
    COALESCE(sa_archive.archived, false) AS is_archived,
    COALESCE(a.infinite_mode, false) AS infinite_mode,
    cd.document_ids,
    COALESCE(tb.copy_paste_allowed, true) AS copy_paste_allowed,
    COALESCE(tb.text_enabled, true) AS text_enabled,
    COALESCE(tb.audio_enabled, true) AS audio_enabled,
    COALESCE(tb.hints_enabled, true) AS hints_enabled,
    COALESCE(tb.show_images, true) AS show_images,
    COALESCE(tb.show_objectives, true) AS show_objectives,
    COALESCE(tb.show_problem_statement, true) AS show_problem_statement,
    COALESCE(ctl.time_limit_seconds, 0) AS time_limit_seconds,
    COALESCE(ctl.negative, false) AS negative,
    cps.problem_statement_id,
    cobj.objective_ids,
    cq.question_ids,
    copt.option_ids,
    cimg.image_ids,
    cvid.video_ids,
    csg.standard_group_ids,
    cstd.standard_ids
   FROM (((((((((((((((((((((((((((((public.attempt_chat_entry c
     LEFT JOIN public.calls_entry cl_grp ON ((cl_grp.id = c.call_id)))
     LEFT JOIN public.runs_entry r_grp ON ((r_grp.id = cl_grp.run_id)))
     JOIN public.attempt_chat_bridge_entry ac ON ((ac.attempt_chat_id = c.id)))
     JOIN public.attempt_entry a ON ((a.id = ac.attempt_id)))
     JOIN public.attempt_profiles_connection apc ON (((apc.attempt_id = a.id) AND (apc.active = true))))
     LEFT JOIN public.attempt_home_entry ahe ON (((ahe.attempt_id = a.id) AND (ahe.active = true))))
     LEFT JOIN public.attempt_practice_entry ape ON (((ape.attempt_id = a.id) AND (ape.active = true))))
     LEFT JOIN public.home_simulations_connection home_sim ON (((home_sim.home_id = ahe.home_id) AND (home_sim.active = true))))
     LEFT JOIN public.practice_simulations_connection prac_sim ON (((prac_sim.practice_id = ape.practice_id) AND (prac_sim.active = true))))
     LEFT JOIN public.home_cohorts_connection home_coh ON (((home_coh.home_id = ahe.home_id) AND (home_coh.active = true))))
     LEFT JOIN public.practice_cohorts_connection prac_coh ON (((prac_coh.practice_id = ape.practice_id) AND (prac_coh.active = true))))
     LEFT JOIN public.home_departments_connection home_dep ON (((home_dep.home_id = ahe.home_id) AND (home_dep.active = true))))
     LEFT JOIN public.practice_departments_connection prac_dep ON (((prac_dep.practice_id = ape.practice_id) AND (prac_dep.active = true))))
     LEFT JOIN chat_scope cs ON ((cs.chat_id = c.id)))
     LEFT JOIN chat_personas cp ON ((cp.chat_id = c.id)))
     LEFT JOIN latest_grade lg ON ((lg.chat_id = c.id)))
     LEFT JOIN chat_rubric cr ON ((cr.attempt_chat_id = c.id)))
     LEFT JOIN chat_documents cd ON ((cd.chat_id = c.id)))
     LEFT JOIN LATERAL ( SELECT attempt_archive_entry.archived
           FROM public.attempt_archive_entry
          WHERE ((attempt_archive_entry.attempt_id = a.id) AND (attempt_archive_entry.active = true))
          ORDER BY attempt_archive_entry.created_at DESC
         LIMIT 1) sa_archive ON (true))
     LEFT JOIN public.chat_entry tb ON ((tb.id = c.chat_id)))
     LEFT JOIN chat_time_limits ctl ON ((ctl.chat_id = c.chat_id)))
     LEFT JOIN chat_problem_statements cps ON ((cps.chat_id = c.id)))
     LEFT JOIN chat_objectives cobj ON ((cobj.chat_id = c.id)))
     LEFT JOIN chat_questions cq ON ((cq.chat_id = c.id)))
     LEFT JOIN chat_options copt ON ((copt.chat_id = c.id)))
     LEFT JOIN chat_images cimg ON ((cimg.chat_id = c.id)))
     LEFT JOIN chat_videos cvid ON ((cvid.chat_id = c.id)))
     LEFT JOIN chat_standard_groups csg ON ((csg.chat_id = c.id)))
     LEFT JOIN chat_standards cstd ON ((cstd.chat_id = c.id)))
  WHERE ((c.active = true) AND (a.active = true))
  WITH NO DATA;

-- ============================================================================
-- Step 6: Recreate test_invocation_mv (group_id derived via call → run)
-- ============================================================================

CREATE MATERIALIZED VIEW public.test_invocation_mv AS
 WITH groups_agents_links AS (
         SELECT ge.test_invocation_id,
            array_agg(DISTINCT gac.agents_id ORDER BY gac.agents_id) FILTER (WHERE (gac.agents_id IS NOT NULL)) AS group_agent_ids
           FROM (public.test_invocation_groups_entry ge
             JOIN public.test_invocation_groups_agents_connection gac ON (((gac.test_invocation_groups_id = ge.id) AND (gac.active = true))))
          WHERE (ge.active = true)
          GROUP BY ge.test_invocation_id
        ), runs_agents_links AS (
         SELECT re.test_invocation_id,
            array_agg(DISTINCT rac.agents_id ORDER BY rac.agents_id) FILTER (WHERE (rac.agents_id IS NOT NULL)) AS run_agent_ids
           FROM (public.test_invocation_runs_entry re
             JOIN public.test_invocation_runs_agents_connection rac ON (((rac.test_invocation_runs_id = re.id) AND (rac.active = true))))
          WHERE (re.active = true)
          GROUP BY re.test_invocation_id
        ), department_links AS (
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
    COALESCE(ral.run_agent_ids, ARRAY[]::uuid[]) AS run_agent_ids,
    COALESCE(gal.group_agent_ids, ARRAY[]::uuid[]) AS group_agent_ids,
    bs.voice_id,
    bs.temperature_level_id,
    bs.reasoning_level_id,
    COALESCE(bs.modality_ids, ARRAY[]::uuid[]) AS modality_ids
   FROM ((((((((public.test_invocation_entry i
     LEFT JOIN public.calls_entry cl_grp ON ((cl_grp.id = i.call_id)))
     LEFT JOIN public.runs_entry r_grp ON ((r_grp.id = cl_grp.run_id)))
     LEFT JOIN groups_agents_links gal ON ((gal.test_invocation_id = i.id)))
     LEFT JOIN runs_agents_links ral ON ((ral.test_invocation_id = i.id)))
     LEFT JOIN department_links dl ON ((dl.test_invocation_id = i.id)))
     LEFT JOIN latest_grade lg ON ((lg.invocation_id = i.id)))
     LEFT JOIN latest_completion lc ON ((lc.invocation_id = i.id)))
     LEFT JOIN bundle_snapshot bs ON ((bs.test_invocation_id = i.id)))
  WHERE (i.active = true)
  WITH NO DATA;
