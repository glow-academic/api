#!/usr/bin/env python3
"""Rewrite 37 resource CREATE SQL functions to use optional tool_id + group_id pattern.

Matches the gold standard pattern from names_complete.sql:
- No agent_id parameter
- Optional group_id and tool_id (DEFAULT NULL)
- Conditional tracking block (runs_entry + calls_entry + connections)
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(
    PROJECT_ROOT, "server", "app", "sql", "v4", "queries", "resources"
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def drop_block(func_name: str) -> str:
    return f"""-- Drop function if exists (handles signature variations)
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT oidvectortypes(proargtypes) as sig
        FROM pg_proc
        WHERE proname = '{func_name}'
          AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    LOOP
        EXECUTE format('DROP FUNCTION IF EXISTS {func_name}(%s)', r.sig);
    END LOOP;
END $$;"""


def tracking_block(resource: str, func_name: str, var_name: str) -> str:
    return f"""    -- If tool_id and group_id provided, create run and call for tracking
    IF tool_id IS NOT NULL AND group_id IS NOT NULL THEN
        -- Create run record
        v_run_id := uuidv7();
        INSERT INTO runs_entry (id, input_tokens, output_tokens, cached_input_tokens, group_id, created_at, updated_at)
        VALUES (v_run_id, 0, 0, 0, {func_name}.group_id, NOW(), NOW());

        -- Create call record
        v_call_id := uuidv7();
        INSERT INTO calls_entry (id, external_call_id, run_id, completed, created_at, updated_at)
        VALUES (v_call_id, '{resource}_' || v_call_id::text, v_run_id, true, NOW(), NOW());

        -- Link tool to call
        INSERT INTO tools_calls_connection (tools_id, call_id) VALUES ({func_name}.tool_id, v_call_id);

        -- Link resource to call
        INSERT INTO {resource}_calls_connection ({resource}_id, call_id)
        VALUES ({var_name}, v_call_id);
    END IF;"""


def generate_sql(
    resource: str,
    comment: str,
    params: str,
    return_col: str,
    var_name: str,
    body: str,
    extra_declares: str = "",
    has_var_conflict: bool = True,
) -> str:
    func_name = f"api_create_{resource}_v4"

    # Build params section
    if params:
        all_params = f"    {params},\n    mcp boolean DEFAULT false,\n    group_id uuid DEFAULT NULL,\n    tool_id uuid DEFAULT NULL"
    else:
        all_params = "    mcp boolean DEFAULT false,\n    group_id uuid DEFAULT NULL,\n    tool_id uuid DEFAULT NULL"

    # DECLARE block
    declares = f"    {var_name} uuid;\n    v_run_id uuid;\n    v_call_id uuid;"
    if extra_declares:
        declares += f"\n{extra_declares}"

    var_conflict = "\n#variable_conflict use_column" if has_var_conflict else ""

    track = tracking_block(resource, func_name, var_name)

    return f"""-- {comment}

{drop_block(func_name)}

CREATE OR REPLACE FUNCTION {func_name}(
{all_params}
)
RETURNS TABLE (
    {return_col} uuid
)
LANGUAGE plpgsql
VOLATILE
AS $${var_conflict}
DECLARE
{declares}
BEGIN
{body}
{track}

    RETURN QUERY SELECT {var_name};
END;
$$;
"""


# ── Resource Configurations ──────────────────────────────────────────────────


def build_configs():
    """Return list of (file_path, sql_content) tuples for all 37 resources."""
    configs = []
    fn = "api_create_{}_v4"

    # ─── Group 1: Always INSERT, no resource-specific fields ─────────────
    always_insert = [
        ("voices", "v_voices_id", "voices_id"),
        ("endpoints", "v_endpoints_id", "endpoints_id"),
        ("values", "v_values_id", "values_id"),
        ("pricing", "v_pricing_id", "pricing_id"),
        ("items", "v_items_id", "items_id"),
        ("protocols", "v_protocols_id", "protocols_id"),
        ("slugs", "v_slugs_id", "slugs_id"),
        ("run_positions", "v_run_positions_id", "run_positions_id"),
        ("group_positions", "v_group_positions_id", "group_positions_id"),
    ]
    for resource, var, ret in always_insert:
        body = f"""    -- INSERT INTO {resource}_resource table
    INSERT INTO {resource}_resource(active, mcp)
    VALUES (true, mcp)
    RETURNING id INTO {var};"""
        configs.append(
            (
                f"{resource}_complete.sql",
                generate_sql(
                    resource=resource,
                    comment=f"Create {resource} resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Always INSERT operation\n-- Parameters: mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: {ret} (uuid)",
                    params="",
                    return_col=ret,
                    var_name=var,
                    body=body,
                ),
            )
        )

    # ─── Group 2: Simple single-field dedup ──────────────────────────────

    # prompts: dedup on name
    configs.append(
        (
            "prompts_complete.sql",
            generate_sql(
                resource="prompts",
                comment="Create prompts resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if name already exists)\n-- Parameters: system_prompt (text), name (text), description (text), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: prompt_id (uuid)",
                params="system_prompt text,\n    name text,\n    description text",
                return_col="prompt_id",
                var_name="v_prompt_id",
                body=f"""    -- Check if prompts already exists (match on name)
    SELECT r.id INTO v_prompt_id
    FROM prompts_resource r
    WHERE r.name = {fn.format("prompts")}.name
    LIMIT 1;

    IF v_prompt_id IS NOT NULL THEN
        RETURN QUERY SELECT v_prompt_id;
        RETURN;
    END IF;

    -- INSERT INTO prompts_resource table
    INSERT INTO prompts_resource(system_prompt, name, description, active, mcp)
    VALUES (system_prompt, name, description, true, mcp)
    RETURNING id INTO v_prompt_id;""",
            ),
        )
    )

    # emails: dedup on email
    configs.append(
        (
            "emails_complete.sql",
            generate_sql(
                resource="emails",
                comment="Create emails resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if email already exists)\n-- Parameters: email (text), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: emails_id (uuid)",
                params="email text",
                return_col="emails_id",
                var_name="v_emails_id",
                body=f"""    -- Check if email already exists
    SELECT er.id INTO v_emails_id
    FROM emails_resource er
    WHERE er.email = {fn.format("emails")}.email
    LIMIT 1;

    IF v_emails_id IS NOT NULL THEN
        RETURN QUERY SELECT v_emails_id;
        RETURN;
    END IF;

    -- INSERT INTO emails_resource table
    INSERT INTO emails_resource(email, active, mcp)
    VALUES ({fn.format("emails")}.email, true, mcp)
    RETURNING id INTO v_emails_id;""",
            ),
        )
    )

    # request_limits: dedup on requests_per_day
    configs.append(
        (
            "request_limits_complete.sql",
            generate_sql(
                resource="request_limits",
                comment="Create request_limits resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if requests_per_day already exists)\n-- Parameters: requests_per_day (integer), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: request_limits_id (uuid)",
                params="requests_per_day integer",
                return_col="request_limits_id",
                var_name="v_request_limits_id",
                body=f"""    -- Check if request_limits already exists (match on requests_per_day)
    SELECT r.id INTO v_request_limits_id
    FROM request_limits_resource r
    WHERE r.requests_per_day = {fn.format("request_limits")}.requests_per_day
    LIMIT 1;

    IF v_request_limits_id IS NOT NULL THEN
        RETURN QUERY SELECT v_request_limits_id;
        RETURN;
    END IF;

    -- INSERT INTO request_limits_resource table
    INSERT INTO request_limits_resource(requests_per_day, active, mcp)
    VALUES (requests_per_day, true, mcp)
    RETURNING id INTO v_request_limits_id;""",
            ),
        )
    )

    # points: dedup on value
    configs.append(
        (
            "points_complete.sql",
            generate_sql(
                resource="points",
                comment="Create points resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if value already exists)\n-- Parameters: value (numeric), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: point_id (uuid)",
                params="value numeric",
                return_col="point_id",
                var_name="v_point_id",
                body=f"""    -- Check if points already exists (match on value)
    SELECT r.id INTO v_point_id
    FROM points_resource r
    WHERE r.value = {fn.format("points")}.value
    LIMIT 1;

    IF v_point_id IS NOT NULL THEN
        RETURN QUERY SELECT v_point_id;
        RETURN;
    END IF;

    -- INSERT INTO points_resource table
    INSERT INTO points_resource(value, active, mcp)
    VALUES (value, true, mcp)
    RETURNING id INTO v_point_id;""",
            ),
        )
    )

    # standard_groups: dedup on name
    configs.append(
        (
            "standard_groups_complete.sql",
            generate_sql(
                resource="standard_groups",
                comment="Create standard_groups resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if name already exists)\n-- Parameters: name (text), short_name (text), description (text), points (numeric), pass_points (numeric), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: standard_group_id (uuid)",
                params="name text,\n    short_name text,\n    description text,\n    points numeric,\n    pass_points numeric",
                return_col="standard_group_id",
                var_name="v_standard_group_id",
                body=f"""    -- Check if standard_groups already exists (match on name)
    SELECT r.id INTO v_standard_group_id
    FROM standard_groups_resource r
    WHERE r.name = {fn.format("standard_groups")}.name
    LIMIT 1;

    IF v_standard_group_id IS NOT NULL THEN
        RETURN QUERY SELECT v_standard_group_id;
        RETURN;
    END IF;

    -- INSERT INTO standard_groups_resource table
    INSERT INTO standard_groups_resource(name, short_name, description, points, pass_points, active, mcp)
    VALUES (name, short_name, description, points, pass_points, true, mcp)
    RETURNING id INTO v_standard_group_id;""",
            ),
        )
    )

    # questions: dedup on question_text, time_value -> time column
    configs.append(
        (
            "questions_complete.sql",
            generate_sql(
                resource="questions",
                comment="Create questions resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if question_text already exists)\n-- Parameters: question_text (text), allow_multiple (boolean), time_value (integer), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: question_id (uuid)",
                params="question_text text,\n    allow_multiple boolean,\n    time_value integer",
                return_col="question_id",
                var_name="v_question_id",
                body=f"""    -- Check if questions already exists (match on question_text)
    SELECT r.id INTO v_question_id
    FROM questions_resource r
    WHERE r.question_text = {fn.format("questions")}.question_text
    LIMIT 1;

    IF v_question_id IS NOT NULL THEN
        RETURN QUERY SELECT v_question_id;
        RETURN;
    END IF;

    -- INSERT INTO questions_resource table
    INSERT INTO questions_resource(question_text, allow_multiple, time, active, mcp)
    VALUES (question_text, allow_multiple, time_value, true, mcp)
    RETURNING id INTO v_question_id;""",
            ),
        )
    )

    # objectives: dedup on objective
    configs.append(
        (
            "objectives_complete.sql",
            generate_sql(
                resource="objectives",
                comment="Create objectives resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if objective already exists)\n-- Parameters: objective (text), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: objective_id (uuid)",
                params="objective text",
                return_col="objective_id",
                var_name="v_objective_id",
                body=f"""    -- Check if objectives already exists (match on objective)
    SELECT r.id INTO v_objective_id
    FROM objectives_resource r
    WHERE r.objective = {fn.format("objectives")}.objective
    LIMIT 1;

    IF v_objective_id IS NOT NULL THEN
        RETURN QUERY SELECT v_objective_id;
        RETURN;
    END IF;

    -- INSERT INTO objectives_resource table
    INSERT INTO objectives_resource(objective, active, mcp)
    VALUES (objective, true, mcp)
    RETURNING id INTO v_objective_id;""",
            ),
        )
    )

    # problem_statements: dedup on name
    configs.append(
        (
            "problem_statements_complete.sql",
            generate_sql(
                resource="problem_statements",
                comment="Create problem_statements resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if name already exists)\n-- Parameters: name (text), problem_statement (text), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: problem_statement_id (uuid)",
                params="name text,\n    problem_statement text",
                return_col="problem_statement_id",
                var_name="v_problem_statement_id",
                body=f"""    -- Check if problem_statements already exists (match on name)
    SELECT r.id INTO v_problem_statement_id
    FROM problem_statements_resource r
    WHERE r.name = {fn.format("problem_statements")}.name
    LIMIT 1;

    IF v_problem_statement_id IS NOT NULL THEN
        RETURN QUERY SELECT v_problem_statement_id;
        RETURN;
    END IF;

    -- INSERT INTO problem_statements_resource table
    INSERT INTO problem_statements_resource(name, problem_statement, active, mcp)
    VALUES (name, problem_statement, true, mcp)
    RETURNING id INTO v_problem_statement_id;""",
            ),
        )
    )

    # videos: dedup on name
    configs.append(
        (
            "videos_complete.sql",
            generate_sql(
                resource="videos",
                comment="Create videos resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if name already exists)\n-- Parameters: name (text), length_seconds (numeric), description (text), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: video_id (uuid)",
                params="name text,\n    length_seconds numeric,\n    description text",
                return_col="video_id",
                var_name="v_video_id",
                body=f"""    -- Check if videos already exists (match on name)
    SELECT r.id INTO v_video_id
    FROM videos_resource r
    WHERE r.name = {fn.format("videos")}.name
    LIMIT 1;

    IF v_video_id IS NOT NULL THEN
        RETURN QUERY SELECT v_video_id;
        RETURN;
    END IF;

    -- INSERT INTO videos_resource table
    INSERT INTO videos_resource(name, length_seconds, description, active, mcp)
    VALUES (name, length_seconds, description, true, mcp)
    RETURNING id INTO v_video_id;""",
            ),
        )
    )

    # ─── Group 3: Multi-field dedup ──────────────────────────────────────

    # options: dedup on (option_text, is_correct)
    configs.append(
        (
            "options_complete.sql",
            generate_sql(
                resource="options",
                comment="Create options resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if option_text + is_correct already exists)\n-- Parameters: option_text (text), is_correct (boolean), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: option_id (uuid)",
                params="option_text text,\n    is_correct boolean",
                return_col="option_id",
                var_name="v_option_id",
                body=f"""    -- Check if options already exists (match on option_text + is_correct)
    SELECT r.id INTO v_option_id
    FROM options_resource r
    WHERE r.option_text = {fn.format("options")}.option_text
      AND r.is_correct = {fn.format("options")}.is_correct
    LIMIT 1;

    IF v_option_id IS NOT NULL THEN
        RETURN QUERY SELECT v_option_id;
        RETURN;
    END IF;

    -- INSERT INTO options_resource table
    INSERT INTO options_resource(option_text, is_correct, active, mcp)
    VALUES (option_text, is_correct, true, mcp)
    RETURNING id INTO v_option_id;""",
            ),
        )
    )

    # ─── Group 4: Resources with FK validation ───────────────────────────

    # args: dedup on name, generated=true
    configs.append(
        (
            "args_complete.sql",
            generate_sql(
                resource="args",
                comment="Create args resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if name already exists)\n-- Parameters: name (text), description (text), field_type (text), required (boolean), default_value (text), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="name text,\n    description text DEFAULT '',\n    field_type text DEFAULT 'string',\n    required boolean DEFAULT false,\n    default_value text DEFAULT ''",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Check if arg already exists
    SELECT ar.id INTO v_resource_id
    FROM args_resource ar
    WHERE ar.name = {fn.format("args")}.name
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT INTO args_resource table
    INSERT INTO args_resource(
        name, description, field_type, required, default_value,
        active, generated, mcp, created_at
    )
    VALUES (
        {fn.format("args")}.name,
        {fn.format("args")}.description,
        {fn.format("args")}.field_type,
        {fn.format("args")}.required,
        {fn.format("args")}.default_value,
        true,
        true,
        mcp,
        NOW()
    )
    RETURNING id INTO v_resource_id;""",
            ),
        )
    )

    # args_outputs: FK args_resource, dedup on (args_id, name)
    configs.append(
        (
            "args_outputs_complete.sql",
            generate_sql(
                resource="args_outputs",
                comment="Create args_outputs resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if args_id/name already exists)\n-- Parameters: args_id (uuid), name (text), template (text), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="args_id uuid,\n    name text,\n    template text DEFAULT ''",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Validate args_id exists
    IF NOT EXISTS (SELECT 1 FROM args_resource WHERE id = {fn.format("args_outputs")}.args_id) THEN
        RAISE EXCEPTION 'Args resource % does not exist', args_id;
    END IF;

    -- Check if args_outputs already exists for args_id/name
    SELECT aor.id INTO v_resource_id
    FROM args_outputs_resource aor
    WHERE aor.args_id = {fn.format("args_outputs")}.args_id
      AND aor.name = {fn.format("args_outputs")}.name
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT INTO args_outputs_resource table
    INSERT INTO args_outputs_resource(
        args_id, name, template,
        active, generated, mcp, created_at
    )
    VALUES (
        {fn.format("args_outputs")}.args_id,
        {fn.format("args_outputs")}.name,
        {fn.format("args_outputs")}.template,
        true,
        true,
        mcp,
        NOW()
    )
    RETURNING id INTO v_resource_id;""",
            ),
        )
    )

    # texts: special - texts_entry with md5 dedup + texts_resource + texts_texts_connection
    configs.append(
        (
            "texts_complete.sql",
            generate_sql(
                resource="texts",
                comment="Create texts resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Creates texts_entry (with content_hash dedup), texts_resource, texts_texts_connection\n-- Parameters: content (text), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: texts_id (uuid)",
                params="content text",
                return_col="texts_id",
                var_name="v_texts_id",
                extra_declares="    v_text_entry_id uuid;\n    v_content_hash text;",
                body="""    -- Get or create texts_entry (dedup by content hash)
    v_content_hash := md5(content);

    SELECT te.id INTO v_text_entry_id
    FROM texts_entry te
    WHERE md5(te.content) = v_content_hash
    LIMIT 1;

    IF v_text_entry_id IS NULL THEN
        INSERT INTO texts_entry (id, content, active, generated, mcp, created_at, updated_at)
        VALUES (uuidv7(), content, true, false, mcp, NOW(), NOW())
        RETURNING id INTO v_text_entry_id;
    END IF;

    -- Create texts_resource
    v_texts_id := uuidv7();
    INSERT INTO texts_resource (id, active, generated, mcp, created_at)
    VALUES (v_texts_id, true, false, mcp, NOW());

    -- Link texts_resource to texts_entry
    INSERT INTO texts_texts_connection (texts_id, text_id, active, created_at, updated_at)
    VALUES (v_texts_id, v_text_entry_id, true, NOW(), NOW());""",
            ),
        )
    )

    # uploads: FK view_uploads_entry, dedup on upload_id
    configs.append(
        (
            "uploads_complete.sql",
            generate_sql(
                resource="uploads",
                comment="Create uploads resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if upload_id already exists)\n-- Parameters: upload_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: uploads_id (uuid)",
                params="upload_id uuid",
                return_col="uploads_id",
                var_name="v_uploads_id",
                body=f"""    -- Validate upload_id exists
    IF NOT EXISTS (SELECT 1 FROM view_uploads_entry WHERE id = upload_id) THEN
        RAISE EXCEPTION 'Upload % does not exist', upload_id;
    END IF;

    -- Check if uploads_resource entry already exists for this upload_id
    SELECT id INTO v_uploads_id
    FROM uploads_resource
    WHERE upload_id = {fn.format("uploads")}.upload_id
    LIMIT 1;

    -- If exists, return existing ID
    IF v_uploads_id IS NOT NULL THEN
        RETURN QUERY SELECT v_uploads_id;
        RETURN;
    END IF;

    -- INSERT INTO uploads_resource table
    INSERT INTO uploads_resource(upload_id, active, mcp)
    VALUES ({fn.format("uploads")}.upload_id, true, mcp)
    RETURNING id INTO v_uploads_id;""",
            ),
        )
    )

    # simulation_positions: FK simulation_artifact, dedup on simulation_id, ON CONFLICT
    configs.append(
        (
            "simulation_positions_complete.sql",
            generate_sql(
                resource="simulation_positions",
                comment="Create simulation_positions resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if simulation_id already exists)\n-- Parameters: simulation_id (uuid), value (integer), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="simulation_id uuid,\n    value integer",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Validate that simulation exists
    IF NOT EXISTS (SELECT 1 FROM simulation_artifact WHERE id = {fn.format("simulation_positions")}.simulation_id) THEN
        RAISE EXCEPTION 'Simulation % does not exist', {fn.format("simulation_positions")}.simulation_id;
    END IF;

    -- Check if simulation_positions already exists (match on simulation_id)
    SELECT r.id INTO v_resource_id
    FROM simulation_positions_resource r
    WHERE r.simulation_id = {fn.format("simulation_positions")}.simulation_id
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT or UPDATE INTO simulation_positions_resource
    INSERT INTO simulation_positions_resource (
        simulation_id,
        value,
        generated,
        mcp,
        created_at
    )
    VALUES (
        {fn.format("simulation_positions")}.simulation_id,
        {fn.format("simulation_positions")}.value,
        true,
        mcp,
        NOW()
    )
    ON CONFLICT (simulation_id, value)
    DO UPDATE SET
        value = EXCLUDED.value,
        generated = EXCLUDED.generated,
        mcp = EXCLUDED.mcp
    RETURNING id INTO v_resource_id;""",
            ),
        )
    )

    # scenario_positions: FK scenarios_resource, dedup on (scenario_id, value)
    configs.append(
        (
            "scenario_positions_complete.sql",
            generate_sql(
                resource="scenario_positions",
                comment="Create scenario_positions resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if scenario_id + value already exists)\n-- Parameters: simulation_id (uuid), scenario_id (uuid), value (integer), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="simulation_id uuid,\n    scenario_id uuid,\n    value integer",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Validate scenario exists
    IF NOT EXISTS (SELECT 1 FROM scenarios_resource WHERE id = {fn.format("scenario_positions")}.scenario_id) THEN
        RAISE EXCEPTION 'Scenario % does not exist', {fn.format("scenario_positions")}.scenario_id;
    END IF;

    -- Check if scenario_positions already exists (match on scenario_id + value)
    SELECT r.id INTO v_resource_id
    FROM scenario_positions_resource r
    WHERE r.scenario_id = {fn.format("scenario_positions")}.scenario_id
      AND r.value = {fn.format("scenario_positions")}.value
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT INTO scenario_positions_resource
    INSERT INTO scenario_positions_resource (
        scenario_id,
        value,
        generated,
        mcp,
        created_at
    )
    VALUES (
        {fn.format("scenario_positions")}.scenario_id,
        {fn.format("scenario_positions")}.value,
        false,
        mcp,
        NOW()
    )
    RETURNING id INTO v_resource_id;""",
            ),
        )
    )

    # scenario_personas: FK scenarios_resource + persona_artifact, dedup on (scenario_id, persona_id)
    configs.append(
        (
            "scenario_personas_complete.sql",
            generate_sql(
                resource="scenario_personas",
                comment="Create scenario_personas resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if scenario_id + persona_id already exists)\n-- Parameters: simulation_id (uuid), scenario_id (uuid), persona_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="simulation_id uuid,\n    scenario_id uuid,\n    persona_id uuid",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Validate scenario exists
    IF NOT EXISTS (SELECT 1 FROM scenarios_resource WHERE id = {fn.format("scenario_personas")}.scenario_id) THEN
        RAISE EXCEPTION 'Scenario % does not exist', {fn.format("scenario_personas")}.scenario_id;
    END IF;

    -- Validate persona exists
    IF NOT EXISTS (SELECT 1 FROM persona_artifact WHERE id = {fn.format("scenario_personas")}.persona_id) THEN
        RAISE EXCEPTION 'Persona % does not exist', {fn.format("scenario_personas")}.persona_id;
    END IF;

    -- Check if scenario_personas already exists (match on scenario_id + persona_id)
    SELECT r.id INTO v_resource_id
    FROM scenario_personas_resource r
    WHERE r.scenario_id = {fn.format("scenario_personas")}.scenario_id
      AND r.persona_id = {fn.format("scenario_personas")}.persona_id
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT INTO scenario_personas_resource
    INSERT INTO scenario_personas_resource (
        scenario_id,
        persona_id,
        generated,
        mcp,
        created_at
    )
    VALUES (
        {fn.format("scenario_personas")}.scenario_id,
        {fn.format("scenario_personas")}.persona_id,
        false,
        mcp,
        NOW()
    )
    RETURNING id INTO v_resource_id;""",
            ),
        )
    )

    # scenario_rubrics: FK scenarios_resource + rubrics_resource, dedup on (scenario_id, rubric_id)
    configs.append(
        (
            "scenario_rubrics_complete.sql",
            generate_sql(
                resource="scenario_rubrics",
                comment="Create scenario_rubrics resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if scenario_id + rubric_id already exists)\n-- Parameters: scenario_id (uuid), rubric_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="scenario_id uuid,\n    rubric_id uuid",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Validate scenario exists
    IF NOT EXISTS (SELECT 1 FROM scenarios_resource WHERE id = {fn.format("scenario_rubrics")}.scenario_id) THEN
        RAISE EXCEPTION 'Scenario % does not exist', {fn.format("scenario_rubrics")}.scenario_id;
    END IF;

    -- Validate rubric exists
    IF NOT EXISTS (SELECT 1 FROM rubrics_resource WHERE id = {fn.format("scenario_rubrics")}.rubric_id) THEN
        RAISE EXCEPTION 'Rubric % does not exist', {fn.format("scenario_rubrics")}.rubric_id;
    END IF;

    -- Check if scenario_rubrics already exists (match on scenario_id + rubric_id)
    SELECT r.id INTO v_resource_id
    FROM scenario_rubrics_resource r
    WHERE r.scenario_id = {fn.format("scenario_rubrics")}.scenario_id
      AND r.rubric_id = {fn.format("scenario_rubrics")}.rubric_id
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT INTO scenario_rubrics_resource
    INSERT INTO scenario_rubrics_resource (
        scenario_id,
        rubric_id,
        active,
        generated,
        mcp,
        created_at
    )
    VALUES (
        {fn.format("scenario_rubrics")}.scenario_id,
        {fn.format("scenario_rubrics")}.rubric_id,
        true,
        false,
        mcp,
        NOW()
    )
    RETURNING id INTO v_resource_id;""",
            ),
        )
    )

    # scenario_time_limits: FK scenarios_resource, dedup on scenario_id, UPDATE existing
    configs.append(
        (
            "scenario_time_limits_complete.sql",
            generate_sql(
                resource="scenario_time_limits",
                comment="Create scenario_time_limits resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (updates existing if scenario_id already exists)\n-- Parameters: scenario_id (uuid), time_limit_seconds (integer), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="scenario_id uuid,\n    time_limit_seconds integer",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Validate scenario exists
    IF NOT EXISTS (SELECT 1 FROM scenarios_resource WHERE id = {fn.format("scenario_time_limits")}.scenario_id) THEN
        RAISE EXCEPTION 'Scenario % does not exist', {fn.format("scenario_time_limits")}.scenario_id;
    END IF;

    -- Check if scenario_time_limits already exists (match on scenario_id)
    SELECT r.id INTO v_resource_id
    FROM scenario_time_limits_resource r
    WHERE r.scenario_id = {fn.format("scenario_time_limits")}.scenario_id
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        -- Update existing record
        UPDATE scenario_time_limits_resource
        SET time_limit_seconds = {fn.format("scenario_time_limits")}.time_limit_seconds,
            mcp = {fn.format("scenario_time_limits")}.mcp
        WHERE id = v_resource_id;

        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT INTO scenario_time_limits_resource
    INSERT INTO scenario_time_limits_resource (
        scenario_id,
        time_limit_seconds,
        generated,
        mcp,
        active,
        created_at
    )
    VALUES (
        {fn.format("scenario_time_limits")}.scenario_id,
        {fn.format("scenario_time_limits")}.time_limit_seconds,
        false,
        mcp,
        true,
        NOW()
    )
    RETURNING id INTO v_resource_id;""",
            ),
        )
    )

    # run_rubrics: FK runs_resource + rubric_artifact, dedup on (run_id, rubric_id), ON CONFLICT
    configs.append(
        (
            "run_rubrics_complete.sql",
            generate_sql(
                resource="run_rubrics",
                comment="Create run_rubrics resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if run_id + rubric_id already exists)\n-- Parameters: run_id (uuid), rubric_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="run_id uuid,\n    rubric_id uuid",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Validate run exists
    IF NOT EXISTS (SELECT 1 FROM runs_resource WHERE id = {fn.format("run_rubrics")}.run_id) THEN
        RAISE EXCEPTION 'Run % does not exist', {fn.format("run_rubrics")}.run_id;
    END IF;

    -- Validate rubric exists
    IF NOT EXISTS (SELECT 1 FROM rubric_artifact WHERE id = {fn.format("run_rubrics")}.rubric_id) THEN
        RAISE EXCEPTION 'Rubric % does not exist', {fn.format("run_rubrics")}.rubric_id;
    END IF;

    -- Check if run_rubrics already exists (match on run_id + rubric_id)
    SELECT r.id INTO v_resource_id
    FROM run_rubrics_resource r
    WHERE r.run_id = {fn.format("run_rubrics")}.run_id
      AND r.rubric_id = {fn.format("run_rubrics")}.rubric_id
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT INTO run_rubrics_resource
    INSERT INTO run_rubrics_resource (
        run_id,
        rubric_id,
        active,
        generated,
        mcp,
        created_at
    )
    VALUES (
        {fn.format("run_rubrics")}.run_id,
        {fn.format("run_rubrics")}.rubric_id,
        true,
        true,
        mcp,
        NOW()
    )
    ON CONFLICT (run_id, rubric_id)
    DO UPDATE SET
        active = true,
        generated = EXCLUDED.generated,
        mcp = EXCLUDED.mcp
    RETURNING run_rubrics_resource.id INTO v_resource_id;""",
            ),
        )
    )

    # role_routes: FK roles_resource + routes_resource, dedup on (role_id, route_id), ON CONFLICT
    configs.append(
        (
            "role_routes_complete.sql",
            generate_sql(
                resource="role_routes",
                comment="Create role_routes resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if role_id + route_id already exists)\n-- Parameters: role_id (uuid), route_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: role_routes_id (uuid)",
                params="role_id uuid,\n    route_id uuid",
                return_col="role_routes_id",
                var_name="v_role_routes_id",
                body=f"""    -- Validate role exists
    IF NOT EXISTS (SELECT 1 FROM roles_resource WHERE id = {fn.format("role_routes")}.role_id) THEN
        RAISE EXCEPTION 'Role % does not exist', {fn.format("role_routes")}.role_id;
    END IF;

    -- Validate route exists
    IF NOT EXISTS (SELECT 1 FROM routes_resource WHERE id = {fn.format("role_routes")}.route_id) THEN
        RAISE EXCEPTION 'Route % does not exist', {fn.format("role_routes")}.route_id;
    END IF;

    -- Check if role_routes already exists (match on role_id + route_id)
    SELECT r.id INTO v_role_routes_id
    FROM role_routes_resource r
    WHERE r.role_id = {fn.format("role_routes")}.role_id
      AND r.route_id = {fn.format("role_routes")}.route_id
    LIMIT 1;

    IF v_role_routes_id IS NOT NULL THEN
        RETURN QUERY SELECT v_role_routes_id;
        RETURN;
    END IF;

    -- INSERT INTO role_routes_resource
    INSERT INTO role_routes_resource (
        role_id,
        route_id,
        active,
        generated,
        mcp,
        created_at
    )
    VALUES (
        {fn.format("role_routes")}.role_id,
        {fn.format("role_routes")}.route_id,
        true,
        true,
        mcp,
        NOW()
    )
    ON CONFLICT (role_id, route_id)
    DO UPDATE SET
        active = true,
        generated = EXCLUDED.generated,
        mcp = EXCLUDED.mcp,
        updated_at = NOW()
    RETURNING id INTO v_role_routes_id;""",
            ),
        )
    )

    # parameter_fields: dedup on (parameter_id, field_id, active), INSERT omits mcp
    configs.append(
        (
            "parameter_fields/parameter_fields_complete.sql",
            generate_sql(
                resource="parameter_fields",
                comment="Create parameter_fields resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if parameter_id + field_id already exists and is active)\n-- Parameters: parameter_id (uuid), field_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: parameter_fields_id (uuid)",
                params="parameter_id uuid,\n    field_id uuid",
                return_col="parameter_fields_id",
                var_name="v_parameter_fields_id",
                body=f"""    -- Check if parameter_fields already exists (match on parameter_id + field_id + active)
    SELECT r.id INTO v_parameter_fields_id
    FROM parameter_fields_resource r
    WHERE r.parameter_id = {fn.format("parameter_fields")}.parameter_id
      AND r.field_id = {fn.format("parameter_fields")}.field_id
      AND r.active = true
    LIMIT 1;

    IF v_parameter_fields_id IS NOT NULL THEN
        RETURN QUERY SELECT v_parameter_fields_id;
        RETURN;
    END IF;

    -- INSERT INTO parameter_fields_resource table
    INSERT INTO parameter_fields_resource(parameter_id, field_id, active, generated)
    VALUES ({fn.format("parameter_fields")}.parameter_id, {fn.format("parameter_fields")}.field_id, true, false)
    RETURNING id INTO v_parameter_fields_id;""",
            ),
        )
    )

    # keys: FK keys table, dedup on key_id
    configs.append(
        (
            "keys_complete.sql",
            generate_sql(
                resource="keys",
                comment="Create keys resource\n-- SIMPLIFIED: No agent_id required, optional tool_id for tracking\n-- Get or create operation (returns existing ID if key_id already exists)\n-- Parameters: key_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="key_id uuid",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Check if keys_resource entry already exists for this key_id
    SELECT r.id INTO v_resource_id
    FROM keys_resource r
    WHERE r.id = {fn.format("keys")}.key_id
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT INTO keys_resource table
    INSERT INTO keys_resource(id, active, generated, mcp)
    VALUES ({fn.format("keys")}.key_id, true, true, mcp)
    RETURNING id INTO v_resource_id;""",
            ),
        )
    )

    # ─── Category C: Minimal pattern, add tracking ───────────────────────

    # images: dedup on name
    configs.append(
        (
            "images_complete.sql",
            generate_sql(
                resource="images",
                comment="Create images resource\n-- SIMPLIFIED: Optional tool_id for tracking\n-- Get or create operation (returns existing ID if name already exists)\n-- Parameters: name (text), description (text), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: image_id (uuid)",
                params="name text,\n    description text",
                return_col="image_id",
                var_name="v_image_id",
                body=f"""    -- Check if images already exists (match on name)
    SELECT r.id INTO v_image_id
    FROM images_resource r
    WHERE r.name = {fn.format("images")}.name
    LIMIT 1;

    IF v_image_id IS NOT NULL THEN
        RETURN QUERY SELECT v_image_id;
        RETURN;
    END IF;

    -- INSERT INTO images_resource table
    INSERT INTO images_resource(name, description, active, mcp)
    VALUES (name, description, true, mcp)
    RETURNING id INTO v_image_id;""",
            ),
        )
    )

    # provider_keys: FK providers_resource + keys_resource, dedup/upsert
    configs.append(
        (
            "provider_keys_complete.sql",
            generate_sql(
                resource="provider_keys",
                comment="Create provider_keys resource\n-- SIMPLIFIED: Optional tool_id for tracking\n-- Get or create operation from provider + key pair\n-- Parameters: provider_id (uuid), key_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: provider_keys_id (uuid)",
                params="provider_id uuid,\n    key_id uuid",
                return_col="provider_keys_id",
                var_name="v_provider_keys_id",
                extra_declares="    v_key text;\n    v_name text;\n    v_description text;",
                has_var_conflict=False,
                body=f"""    IF NOT EXISTS (SELECT 1 FROM providers_resource p WHERE p.id = {fn.format("provider_keys")}.provider_id) THEN
        RAISE EXCEPTION 'Provider resource not found: %', {fn.format("provider_keys")}.provider_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM keys_resource k WHERE k.id = {fn.format("provider_keys")}.key_id) THEN
        RAISE EXCEPTION 'Key resource not found: %', {fn.format("provider_keys")}.key_id;
    END IF;

    SELECT
        COALESCE(k.key, ''),
        COALESCE(k.name, ''),
        COALESCE(k.description, '')
    INTO v_key, v_name, v_description
    FROM keys_resource k
    WHERE k.id = {fn.format("provider_keys")}.key_id
    LIMIT 1;

    SELECT pkr.id
    INTO v_provider_keys_id
    FROM provider_keys_resource pkr
    WHERE pkr.provider_id = {fn.format("provider_keys")}.provider_id
      AND pkr.key_id = {fn.format("provider_keys")}.key_id
    ORDER BY pkr.created_at DESC
    LIMIT 1;

    IF v_provider_keys_id IS NOT NULL THEN
        UPDATE provider_keys_resource
        SET
            active = true,
            mcp = {fn.format("provider_keys")}.mcp,
            key = v_key,
            name = v_name,
            description = v_description
        WHERE id = v_provider_keys_id;

        RETURN QUERY SELECT v_provider_keys_id;
        RETURN;
    END IF;

    INSERT INTO provider_keys_resource (
        provider_id,
        key_id,
        active,
        generated,
        mcp,
        key,
        name,
        description
    )
    VALUES (
        {fn.format("provider_keys")}.provider_id,
        {fn.format("provider_keys")}.key_id,
        true,
        false,
        {fn.format("provider_keys")}.mcp,
        v_key,
        v_name,
        v_description
    )
    RETURNING id INTO v_provider_keys_id;""",
            ),
        )
    )

    # auth_item_keys: FK auths_resource + items_resource + keys_resource, dedup/upsert
    configs.append(
        (
            "auth_item_keys_complete.sql",
            generate_sql(
                resource="auth_item_keys",
                comment="Create auth_item_keys resource\n-- SIMPLIFIED: Optional tool_id for tracking\n-- Get or create operation from auth + item + key tuple\n-- Parameters: auth_id (uuid), item_id (uuid), key_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: auth_item_keys_id (uuid)",
                params="auth_id uuid,\n    item_id uuid,\n    key_id uuid",
                return_col="auth_item_keys_id",
                var_name="v_auth_item_keys_id",
                has_var_conflict=False,
                body=f"""    IF NOT EXISTS (SELECT 1 FROM auths_resource a WHERE a.id = {fn.format("auth_item_keys")}.auth_id) THEN
        RAISE EXCEPTION 'Auth resource not found: %', {fn.format("auth_item_keys")}.auth_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM items_resource i WHERE i.id = {fn.format("auth_item_keys")}.item_id) THEN
        RAISE EXCEPTION 'Item resource not found: %', {fn.format("auth_item_keys")}.item_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM keys_resource k WHERE k.id = {fn.format("auth_item_keys")}.key_id) THEN
        RAISE EXCEPTION 'Key resource not found: %', {fn.format("auth_item_keys")}.key_id;
    END IF;

    SELECT akr.id
    INTO v_auth_item_keys_id
    FROM auth_item_keys_resource akr
    WHERE akr.auth_id = {fn.format("auth_item_keys")}.auth_id
      AND akr.item_id = {fn.format("auth_item_keys")}.item_id
      AND akr.key_id = {fn.format("auth_item_keys")}.key_id
    ORDER BY akr.created_at DESC
    LIMIT 1;

    IF v_auth_item_keys_id IS NOT NULL THEN
        UPDATE auth_item_keys_resource
        SET
            active = true,
            mcp = {fn.format("auth_item_keys")}.mcp,
            updated_at = NOW()
        WHERE id = v_auth_item_keys_id;

        RETURN QUERY SELECT v_auth_item_keys_id;
        RETURN;
    END IF;

    INSERT INTO auth_item_keys_resource (
        auth_id,
        item_id,
        key_id,
        active,
        generated,
        mcp
    )
    VALUES (
        {fn.format("auth_item_keys")}.auth_id,
        {fn.format("auth_item_keys")}.item_id,
        {fn.format("auth_item_keys")}.key_id,
        true,
        false,
        {fn.format("auth_item_keys")}.mcp
    )
    RETURNING id INTO v_auth_item_keys_id;""",
            ),
        )
    )

    # arg_positions: FK args_resource, dedup/upsert
    configs.append(
        (
            "arg_positions_complete.sql",
            generate_sql(
                resource="arg_positions",
                comment="Create/update arg_positions resource\n-- SIMPLIFIED: Optional tool_id for tracking\n-- Parameters: args_id (uuid), value (integer), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="args_id uuid,\n    value integer",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Validate args_id exists
    IF NOT EXISTS (SELECT 1 FROM args_resource WHERE id = {fn.format("arg_positions")}.args_id) THEN
        RAISE EXCEPTION 'Arg % does not exist', {fn.format("arg_positions")}.args_id;
    END IF;

    -- Check if arg_position already exists for this args_id
    SELECT ap.id
    INTO v_resource_id
    FROM arg_positions_resource ap
    WHERE ap.args_id = {fn.format("arg_positions")}.args_id
      AND ap.active = true
    LIMIT 1;

    IF v_resource_id IS NULL THEN
        -- Create new arg_positions resource
        INSERT INTO arg_positions_resource (id, args_id, value, active, generated, mcp, created_at)
        VALUES (uuidv7(), {fn.format("arg_positions")}.args_id, {fn.format("arg_positions")}.value, true, true, mcp, NOW())
        RETURNING arg_positions_resource.id INTO v_resource_id;
    ELSE
        -- Update existing arg_positions resource
        UPDATE arg_positions_resource
        SET value = {fn.format("arg_positions")}.value,
            active = true,
            generated = true,
            mcp = {fn.format("arg_positions")}.mcp
        WHERE arg_positions_resource.id = v_resource_id;
    END IF;""",
            ),
        )
    )

    # group_rubrics: dedup on (group_id, rubric_id), ON CONFLICT
    configs.append(
        (
            "group_rubrics_complete.sql",
            generate_sql(
                resource="group_rubrics",
                comment="Create group_rubrics resource\n-- SIMPLIFIED: Optional tool_id for tracking\n-- Get or create operation (returns existing ID if group_id + rubric_id already exists)\n-- Parameters: target_group_id (uuid), rubric_id (uuid), mcp (boolean), group_id (uuid, optional), tool_id (uuid, optional)\n-- Returns: id (uuid)",
                params="target_group_id uuid,\n    rubric_id uuid",
                return_col="id",
                var_name="v_resource_id",
                body=f"""    -- Check if group_rubrics already exists (match on group_id + rubric_id)
    SELECT r.id INTO v_resource_id
    FROM group_rubrics_resource r
    WHERE r.group_id = {fn.format("group_rubrics")}.target_group_id
      AND r.rubric_id = {fn.format("group_rubrics")}.rubric_id
    LIMIT 1;

    IF v_resource_id IS NOT NULL THEN
        RETURN QUERY SELECT v_resource_id;
        RETURN;
    END IF;

    -- INSERT INTO group_rubrics_resource table
    INSERT INTO group_rubrics_resource (
        group_id,
        rubric_id,
        active,
        generated,
        mcp,
        created_at
    )
    VALUES (
        {fn.format("group_rubrics")}.target_group_id,
        {fn.format("group_rubrics")}.rubric_id,
        true,
        true,
        mcp,
        NOW()
    )
    ON CONFLICT (group_id, rubric_id)
    DO UPDATE SET
        active = true,
        generated = EXCLUDED.generated,
        mcp = EXCLUDED.mcp
    RETURNING group_rubrics_resource.id INTO v_resource_id;""",
            ),
        )
    )

    return configs


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    configs = build_configs()

    for rel_path, sql_content in configs:
        filepath = os.path.join(SQL_DIR, rel_path)

        if not os.path.exists(filepath):
            print(f"WARNING: File not found: {filepath}")
            continue

        with open(filepath, "w") as f:
            f.write(sql_content)

        print(f"  ✓ {rel_path}")

    print(f"\nDone. Rewrote {len(configs)} files.")


if __name__ == "__main__":
    main()
