-- Parity check before dropping legacy simulation_chats_*_connection tables.
-- Run manually via psql after migration/backfill and before DROP TABLE.

WITH chat_scope AS (
    SELECT
        c.id AS chat_id,
        c.training_bundle_department_id,
        msc.scenario_id,
        msc.rubric_id,
        msc.problem_statement_id,
        COALESCE(msc.persona_ids, ARRAY[]::uuid[]) AS persona_ids,
        COALESCE(msc.document_ids, ARRAY[]::uuid[]) AS document_ids,
        COALESCE(msc.standard_group_ids, ARRAY[]::uuid[]) AS standard_group_ids,
        COALESCE(msc.standard_ids, ARRAY[]::uuid[]) AS standard_ids
    FROM simulation_chats_entry c
    LEFT JOIN mv_simulation_chats msc ON msc.chat_id = c.id
    WHERE c.active = true
),
legacy AS (
    SELECT
        c.id AS chat_id,
        MAX(csc.scenarios_id) FILTER (WHERE csc.active) AS scenario_id,
        MAX(crc.rubrics_id) FILTER (WHERE crc.active) AS rubric_id,
        MAX(cps.problem_statements_id) FILTER (WHERE cps.active) AS problem_statement_id,
        COALESCE(ARRAY_AGG(DISTINCT cpc.personas_id) FILTER (WHERE cpc.active), ARRAY[]::uuid[]) AS persona_ids,
        COALESCE(ARRAY_AGG(DISTINCT cdc.documents_id) FILTER (WHERE cdc.active), ARRAY[]::uuid[]) AS document_ids,
        COALESCE(ARRAY_AGG(DISTINCT csg.standard_groups_id) FILTER (WHERE csg.active), ARRAY[]::uuid[]) AS standard_group_ids,
        COALESCE(ARRAY_AGG(DISTINCT cst.standards_id) FILTER (WHERE cst.active), ARRAY[]::uuid[]) AS standard_ids
    FROM simulation_chats_entry c
    LEFT JOIN simulation_chats_scenarios_connection csc ON csc.chat_id = c.id
    LEFT JOIN simulation_chats_rubrics_connection crc ON crc.chat_id = c.id
    LEFT JOIN simulation_chats_problem_statements_connection cps ON cps.chat_id = c.id
    LEFT JOIN simulation_chats_personas_connection cpc ON cpc.chat_id = c.id
    LEFT JOIN simulation_chats_documents_connection cdc ON cdc.chat_id = c.id
    LEFT JOIN simulation_chats_standard_groups_connection csg ON csg.chat_id = c.id
    LEFT JOIN simulation_chats_standards_connection cst ON cst.chat_id = c.id
    WHERE c.active = true
    GROUP BY c.id
),
cmp AS (
    SELECT
        cs.chat_id,
        (cs.scenario_id IS DISTINCT FROM l.scenario_id) AS scenario_mismatch,
        (cs.rubric_id IS DISTINCT FROM l.rubric_id) AS rubric_mismatch,
        (cs.problem_statement_id IS DISTINCT FROM l.problem_statement_id) AS problem_statement_mismatch,
        (cs.persona_ids IS DISTINCT FROM l.persona_ids) AS persona_mismatch,
        (cs.document_ids IS DISTINCT FROM l.document_ids) AS document_mismatch,
        (cs.standard_group_ids IS DISTINCT FROM l.standard_group_ids) AS standard_group_mismatch,
        (cs.standard_ids IS DISTINCT FROM l.standard_ids) AS standard_mismatch,
        (cs.training_bundle_department_id IS NULL) AS missing_training_bundle_department_id
    FROM chat_scope cs
    LEFT JOIN legacy l ON l.chat_id = cs.chat_id
)
SELECT
    COUNT(*) AS total_chats,
    COUNT(*) FILTER (WHERE missing_training_bundle_department_id) AS chats_missing_training_bundle_department,
    COUNT(*) FILTER (WHERE scenario_mismatch) AS scenario_mismatch_count,
    COUNT(*) FILTER (WHERE rubric_mismatch) AS rubric_mismatch_count,
    COUNT(*) FILTER (WHERE problem_statement_mismatch) AS problem_statement_mismatch_count,
    COUNT(*) FILTER (WHERE persona_mismatch) AS persona_mismatch_count,
    COUNT(*) FILTER (WHERE document_mismatch) AS document_mismatch_count,
    COUNT(*) FILTER (WHERE standard_group_mismatch) AS standard_group_mismatch_count,
    COUNT(*) FILTER (WHERE standard_mismatch) AS standard_mismatch_count
FROM cmp;
