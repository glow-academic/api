#!/usr/bin/env python3
"""Generate migration 494: Agent Setup & Prompt Updates.

Connects to the local database to query current state, reads prompt .jinja
files from disk, and writes the migration SQL to database/migrate/494_agent_setup.sql.

Usage:
    python scripts/generate_migration_494.py
"""

from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
OUTPUT = ROOT / "database" / "migrate" / "494_agent_setup.sql"
DB_DSN = "postgresql://myuser:mypassword@localhost:5432/mydb"

# ─── Well-known IDs ──────────────────────────────────────────────────────────
GPT41_MODEL_ID = "019bb25e-e5ff-76f6-90d4-830670bb5d82"
AGENT_ACTIVE_FLAG = "019be334-bfc4-76ac-80d3-c8ba7618bc7a"
TOOL_ACTIVE_FLAG = "019be334-bfc6-74fb-be11-ea6b522945bb"
SETTINGS = [
    "019c3f8c-b97c-7fa5-b369-7d7418bedbcf",  # General Settings
    "019b3be4-3c61-76ff-befb-69b082df2acd",  # Purdue CS Settings
]

# Existing agent artifact IDs that need fixes
TRAINING_AGENT_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
CHAT_AGENT_ID = "ee000001-eeee-eeee-eeee-eeeeeeeeeeee"
GRADE_AGENT_ID = "ff000001-ffff-ffff-ffff-ffffffffffff"
EVAL_AGENT_ID = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
FIELD_AGENT_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

# ─── New agent artifact UUIDs ────────────────────────────────────────────────
NEW_AGENTS = {
    "Invocation": "ab000001-0000-0000-0000-000000000001",
    "Attempt Chat": "ab000002-0000-0000-0000-000000000002",
    "Attempt Grade": "ab000003-0000-0000-0000-000000000003",
    "Test": "ab000004-0000-0000-0000-000000000004",
    "Home": "ab000005-0000-0000-0000-000000000005",
    "Practice": "ab000006-0000-0000-0000-000000000006",
    "Dashboard": "ab000007-0000-0000-0000-000000000007",
    "Reports": "ab000008-0000-0000-0000-000000000008",
    "Record": "ab000009-0000-0000-0000-000000000009",
    "Activity": "ab00000a-0000-0000-0000-00000000000a",
    "Session": "ab00000b-0000-0000-0000-00000000000b",
    "Pricing": "ab00000c-0000-0000-0000-00000000000c",
    "Health": "ab00000d-0000-0000-0000-00000000000d",
    "Leaderboard": "ab00000e-0000-0000-0000-00000000000e",
    "Group": "ab00000f-0000-0000-0000-00000000000f",
}

# ─── Agent → prompt file stem ────────────────────────────────────────────────
PROMPT_FILE = {
    # Existing agents (display name → file stem)
    "Agent": "agent",
    "Auth": "auth",
    "Benchmark": "benchmark",
    "Chat": "chat",  # renamed from Training
    "Cohort": "cohort",
    "Department": "department",
    "Document": "document",
    "Eval": "eval",
    "Field": "field",
    "Model": "model",
    "Parameter": "parameter",
    "Persona": "persona",
    "Profile": "profile",
    "Provider": "provider",
    "Rubric": "rubric",
    "Scenario": "scenario",
    "Setting": "setting",
    "Simulation": "simulation",
    "Tool": "tool",
    # New agents
    "Invocation": "invocation",
    "Attempt Chat": "attempt-chat",
    "Attempt Grade": "attempt-grade",
    "Test": "test",
    "Home": "home",
    "Practice": "practice",
    "Dashboard": "dashboard",
    "Reports": "reports",
    "Record": "record",
    "Activity": "activity",
    "Session": "session",
    "Pricing": "pricing",
    "Health": "health",
    "Leaderboard": "leaderboard",
    "Group": "group",
}


# ─── Agent → expected tools_resource.name list ───────────────────────────────
# Derived from each agent's system prompt tool listings
def _crud(resources: list[str]) -> list[str]:
    """Generate create_* + use_* tool names for a list of resources."""
    tools = []
    for r in resources:
        tools.append(f"create_{r}")
        tools.append(f"use_{r}")
    return tools


AGENT_TOOLS: dict[str, list[str]] = {
    "Agent": _crud(
        [
            "names",
            "descriptions",
            "models",
            "prompts",
            "instructions",
            "flags",
            "departments",
            "tools",
            "temperature_levels",
            "reasoning_levels",
            "voices",
        ]
    ),
    "Auth": _crud(
        ["names", "descriptions", "flags", "departments", "items", "protocols", "slugs"]
    ),
    "Benchmark": [
        "create_names",
        "create_descriptions",
        "create_instructions",
        "create_models",
        "create_prompt",
        "create_keys",
        "create_reasoning_levels",
        "create_temperature_levels",
        "create_voices",
        "use_names",
        "use_descriptions",
        "use_flags",
        "use_departments",
        "use_instructions",
    ],
    "Chat": _crud(
        [
            "names",
            "descriptions",
            "flags",
            "departments",
            "personas",
            "documents",
            "scenarios",
            "parameter_fields",
            "parameters",
            "fields",
            "questions",
            "options",
            "videos",
            "images",
            "objectives",
            "problem_statements",
        ]
    ),
    "Cohort": _crud(
        [
            "names",
            "descriptions",
            "flags",
            "departments",
            "simulations",
            "simulation_positions",
            "simulation_availability",
        ]
    ),
    "Department": _crud(["names", "descriptions", "flags", "settings"]),
    "Document": _crud(
        [
            "names",
            "descriptions",
            "flags",
            "departments",
            "images",
            "parameter_fields",
            "parameters",
            "texts",
            "uploads",
        ]
    ),
    "Eval": _crud(
        [
            "names",
            "descriptions",
            "flags",
            "departments",
            "runs",
            "run_positions",
            "runs_rubrics",
            "groups",
            "group_positions",
            "groups_rubrics",
        ]
    ),
    "Field": _crud(
        ["names", "descriptions", "flags", "departments", "conditional_parameters"]
    ),
    "Model": _crud(
        [
            "names",
            "descriptions",
            "values",
            "providers",
            "flags",
            "departments",
            "modalities",
            "temperature_levels",
            "pricing",
            "reasoning_levels",
            "qualities",
            "voices",
        ]
    ),
    "Parameter": _crud(["names", "descriptions", "flags", "departments", "fields"]),
    "Persona": _crud(
        [
            "names",
            "descriptions",
            "colors",
            "icons",
            "instructions",
            "flags",
            "examples",
            "parameter_fields",
            "departments",
            "parameters",
        ]
    ),
    "Profile": _crud(
        [
            "names",
            "flags",
            "departments",
            "emails",
            "cohorts",
            "request_limits",
            "roles",
        ]
    ),
    "Provider": _crud(
        ["names", "descriptions", "flags", "departments", "values", "endpoints", "keys"]
    ),
    "Rubric": _crud(
        [
            "names",
            "descriptions",
            "flags",
            "departments",
            "points",
            "standard_groups",
            "standards",
        ]
    ),
    "Scenario": _crud(
        [
            "names",
            "descriptions",
            "flags",
            "departments",
            "documents",
            "images",
            "objectives",
            "options",
            "parameter_fields",
            "parameters",
            "personas",
            "problem_statements",
            "questions",
            "videos",
        ]
    ),
    "Setting": _crud(
        [
            "names",
            "descriptions",
            "colors",
            "flags",
            "departments",
            "agents",
            "auths",
            "auth_item_keys",
            "auth_values",
            "profiles",
            "provider_keys",
            "thresholds",
        ]
    ),
    "Simulation": _crud(
        [
            "names",
            "descriptions",
            "flags",
            "departments",
            "scenarios",
            "scenario_flags",
            "scenario_personas",
            "scenario_positions",
            "scenario_rubrics",
            "scenario_time_limits",
        ]
    ),
    "Tool": _crud(
        [
            "names",
            "descriptions",
            "flags",
            "departments",
            "args",
            "arg_positions",
            "args_outputs",
            "bindings",
            "domains",
        ]
    ),
    # New agents
    "Invocation": _crud(
        [
            "names",
            "descriptions",
            "flags",
            "departments",
            "models",
            "prompts",
            "instructions",
            "runs",
            "groups",
            "keys",
            "tools",
            "temperature_levels",
            "reasoning_levels",
            "voices",
        ]
    ),
    "Attempt Chat": ["create_content", "create_hint", "end_conversation"],
    "Attempt Grade": [
        "create_feedback",
        "create_strength",
        "create_improvement",
        "create_analysis",
        "create_highlight",
        "create_replacement",
    ],
    "Test": ["create_feedback"],
    "Home": ["create_insights"],
    "Practice": ["create_insights"],
    "Dashboard": ["create_insights"],
    "Reports": ["create_insights"],
    "Record": ["create_insights"],
    "Activity": ["create_insights"],
    "Session": ["create_insights"],
    "Pricing": ["create_insights"],
    "Health": ["create_insights"],
    "Leaderboard": ["create_insights"],
    "Group": ["create_insights"],
}

# ─── Agent descriptions ──────────────────────────────────────────────────────
AGENT_DESC: dict[str, str] = {
    "Agent": "AI agent for creating and managing agent artifacts with models, prompts, instructions, and tool bindings",
    "Auth": "AI agent for creating and managing authentication configurations with protocols, slugs, and items",
    "Benchmark": "AI agent for benchmark configuration and evaluation run setup",
    "Chat": "AI agent for creating and managing training chat sessions with persona-driven scenario conversations",
    "Cohort": "AI agent for creating and managing cohorts grouping simulations for training programs",
    "Department": "AI agent for creating and managing organizational departments with settings",
    "Document": "AI agent for creating and managing documents with uploads, images, and text content",
    "Eval": "AI agent for creating and managing evaluation configurations with runs, groups, and rubric bindings",
    "Field": "AI agent for creating and managing fields with conditional parameter logic for dynamic forms",
    "Model": "AI agent for creating and managing AI model configurations with providers and capabilities",
    "Parameter": "AI agent for creating and managing parameters with associated fields for dynamic configuration",
    "Persona": "AI agent for creating and managing personas for AI-powered simulations and interactions",
    "Profile": "AI agent for creating and managing user profiles with department assignments and roles",
    "Provider": "AI agent for creating and managing AI provider configurations with endpoints and API keys",
    "Rubric": "AI agent for creating and managing grading rubrics with standard groups and point values",
    "Scenario": "AI agent for creating and managing training scenarios with problem statements and objectives",
    "Setting": "AI agent for creating and managing system settings with auth, provider keys, and departments",
    "Simulation": "AI agent for creating and managing simulation configurations with scenario orderings and rubrics",
    "Tool": "AI agent for creating and managing tool definitions with arguments and output mappings",
    "Invocation": "AI agent for creating and managing benchmark invocations with model and tool configurations",
    "Attempt Chat": "Conversational AI agent for conducting training dialogues as personas",
    "Attempt Grade": "Grading and evaluation agent for analyzing training attempt performance",
    "Test": "Benchmark test grading agent for evaluating model outputs against rubric standards",
    "Home": "Navigation and recommendation agent for home page overview",
    "Practice": "Navigation and recommendation agent for practice mode entry point",
    "Dashboard": "Analytical insights agent for high-level organizational KPIs and trends",
    "Reports": "Analytical insights agent for detailed training outcome reports",
    "Record": "Analytical insights agent for individual training record analytics",
    "Activity": "Analytical insights agent for real-time activity monitoring",
    "Session": "Analytical insights agent for individual training session analytics",
    "Pricing": "Analytical insights agent for cost analytics and billing breakdowns",
    "Health": "Analytical insights agent for system health monitoring",
    "Leaderboard": "Analytical insights agent for performance rankings",
    "Group": "Analytical insights agent for group-level analytics",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def dollar_quote(text: str) -> str:
    """Wrap text in a dollar-quoted string, choosing a safe tag."""
    tag = "body"
    i = 0
    while f"${tag}$" in text:
        i += 1
        tag = f"body{i}"
    return f"${tag}${text}${tag}$"


def sql_literal(text: str) -> str:
    """Escape a string for SQL single-quote literal."""
    return "'" + text.replace("'", "''") + "'"


def read_prompt(stem: str, kind: str) -> str:
    """Read prompts/{stem}.{kind}.jinja, return content or empty string."""
    path = PROMPTS_DIR / f"{stem}.{kind}.jinja"
    return path.read_text() if path.exists() else ""


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()

    # ── Query 1: tool name → tools_resource.id + tool_artifact.id ──
    cur.execute("""
        SELECT tr.id, tr.name, ta.id
        FROM tools_resource tr
        JOIN tool_tools_junction ttj ON ttj.tools_id = tr.id
        JOIN tool_artifact ta ON ta.id = ttj.tool_id
    """)
    tools_res_id: dict[str, str] = {}  # tool name → tools_resource.id
    tools_art_id: dict[str, str] = {}  # tool name → tool_artifact.id
    for tr_id, name, ta_id in cur.fetchall():
        tools_res_id[name] = str(tr_id)
        tools_art_id[name] = str(ta_id)

    # ── Query 2: existing agents with all their state ──
    cur.execute("""
        SELECT aa.id, nr.name,
               aaj.agents_id,
               apj.prompt_id,
               STRING_AGG(DISTINCT aij.instruction_id::text, ',')
        FROM agent_artifact aa
        JOIN agent_names_junction anj ON anj.agent_id = aa.id
        JOIN names_resource nr ON nr.id = anj.name_id
        LEFT JOIN agent_agents_junction aaj ON aaj.agent_id = aa.id
        LEFT JOIN agent_prompts_junction apj ON apj.agent_id = aa.id
        LEFT JOIN agent_instructions_junction aij ON aij.agent_id = aa.id
        GROUP BY aa.id, nr.name, aaj.agents_id, apj.prompt_id
    """)
    existing: dict[str, dict] = {}
    for row in cur.fetchall():
        agent_id, name, agents_res_id, prompt_id, instr_ids_str = row
        instr_ids = instr_ids_str.split(",") if instr_ids_str else []
        existing[name] = {
            "agent_id": str(agent_id),
            "agents_resource_id": str(agents_res_id) if agents_res_id else None,
            "prompt_id": str(prompt_id) if prompt_id else None,
            "instruction_ids": instr_ids,
        }

    # ── Query 3: existing agent→tool mappings ──
    cur.execute("""
        SELECT nr.name AS agent_name, tr.name AS tool_name
        FROM agent_tools_junction atj
        JOIN agent_names_junction anj ON anj.agent_id = atj.agent_id
        JOIN names_resource nr ON nr.id = anj.name_id
        JOIN tools_resource tr ON tr.id = atj.tool_id
    """)
    existing_tools: dict[str, set[str]] = {}
    for agent_name, tool_name in cur.fetchall():
        existing_tools.setdefault(agent_name, set()).add(tool_name)

    # ── Query 4: existing setting_agents_junction entries ──
    cur.execute("""
        SELECT setting_id, agents_id FROM setting_agents_junction
    """)
    existing_setting_agents: set[tuple[str, str]] = set()
    for sid, aid in cur.fetchall():
        existing_setting_agents.add((str(sid), str(aid)))

    conn.close()

    # ── Validate tool names ──
    all_missing_tools: dict[str, list[str]] = {}
    for agent_name, expected in AGENT_TOOLS.items():
        for t in expected:
            if t not in tools_res_id:
                all_missing_tools.setdefault(agent_name, []).append(t)
    if all_missing_tools:
        print("WARNING: Some expected tools don't exist in DB:")
        for agent, missing in all_missing_tools.items():
            print(f"  {agent}: {missing}")
        print("These tools will be skipped in the migration.")
        print()

    # ═══════════════════════════════════════════════════════════════
    # BUILD SQL
    # ═══════════════════════════════════════════════════════════════
    sql: list[str] = []

    sql.append("-- Migration 494: Agent Setup & Prompt Updates")
    sql.append("-- Auto-generated by scripts/generate_migration_494.py")
    sql.append("-- DO NOT EDIT MANUALLY — regenerate instead.")
    sql.append("")
    sql.append("BEGIN;")
    sql.append("")

    # ═══ STEP 1: Fix tool naming gap from migration 493 ═══════════
    sql.append(
        "-- ═══ STEP 1: Add names/descriptions/flags for tools from migration 493 ═══"
    )
    sql.append("")
    sql.append("""DO $$
DECLARE
    r RECORD;
    v_name_id uuid;
    v_desc_id uuid;
    v_description text;
BEGIN
    FOR r IN
        SELECT ta.id AS tool_id, tr.name AS tool_name
        FROM tool_artifact ta
        JOIN tool_tools_junction ttj ON ttj.tool_id = ta.id
        JOIN tools_resource tr ON tr.id = ttj.tools_id
        WHERE NOT EXISTS (SELECT 1 FROM tool_names_junction tnj WHERE tnj.tool_id = ta.id)
    LOOP
        -- Derive description from tool name
        IF r.tool_name LIKE 'create_%' THEN
            v_description := 'Create a new ' || REPLACE(SUBSTRING(r.tool_name FROM 8), '_', ' ') || ' resource';
        ELSIF r.tool_name LIKE 'use_%' THEN
            v_description := 'Use an existing ' || REPLACE(SUBSTRING(r.tool_name FROM 5), '_', ' ') || ' resource instead of creating a new one';
        ELSE
            v_description := r.tool_name;
        END IF;

        -- Reuse existing name if it exists, otherwise create
        SELECT id INTO v_name_id FROM names_resource WHERE name = r.tool_name LIMIT 1;
        IF v_name_id IS NULL THEN
            INSERT INTO names_resource (name) VALUES (r.tool_name) RETURNING id INTO v_name_id;
        END IF;
        INSERT INTO tool_names_junction (tool_id, name_id) VALUES (r.tool_id, v_name_id) ON CONFLICT DO NOTHING;

        INSERT INTO descriptions_resource (description) VALUES (v_description) RETURNING id INTO v_desc_id;
        INSERT INTO tool_descriptions_junction (tool_id, description_id) VALUES (r.tool_id, v_desc_id) ON CONFLICT DO NOTHING;

        INSERT INTO tool_flags_junction (tool_id, flag_id, value)
        VALUES (r.tool_id, '019be334-bfc6-74fb-be11-ea6b522945bb', true)
        ON CONFLICT DO NOTHING;
    END LOOP;
END $$;""")
    sql.append("")

    # ═══ STEP 2: Rename Training → Chat ═══════════════════════════
    sql.append("-- ═══ STEP 2: Rename Training → Chat ═══")
    sql.append("")
    sql.append(f"""UPDATE names_resource SET name = 'Chat'
WHERE id = (SELECT name_id FROM agent_names_junction WHERE agent_id = '{TRAINING_AGENT_ID}');""")
    sql.append("")
    # Update description too
    training_desc = AGENT_DESC["Chat"]
    sql.append(f"""UPDATE descriptions_resource SET description = {sql_literal(training_desc)}
WHERE id = (SELECT description_id FROM agent_descriptions_junction WHERE agent_id = '{TRAINING_AGENT_ID}');""")
    sql.append("")

    # ═══ STEP 3: Disable old Chat Agent and Grade Agent ═══════════
    sql.append("-- ═══ STEP 3: Disable old Chat Agent and Grade Agent ═══")
    sql.append("")
    sql.append(f"""UPDATE agent_flags_junction SET value = false
WHERE agent_id IN ('{CHAT_AGENT_ID}', '{GRADE_AGENT_ID}')
  AND flag_id = '{AGENT_ACTIVE_FLAG}';""")
    sql.append("")

    # ═══ STEP 4: Fix Eval agent (create own resources) ════════════
    sql.append("-- ═══ STEP 4: Fix Eval agent — create its own resources ═══")
    _emit_fix_agent(sql, "Eval", EVAL_AGENT_ID, existing, tools_res_id)

    # ═══ STEP 5: Fix Field agent (create own resources) ═══════════
    sql.append("-- ═══ STEP 5: Fix Field agent — create its own resources ═══")
    _emit_fix_agent(sql, "Field", FIELD_AGENT_ID, existing, tools_res_id)

    # ═══ STEP 6: Create 15 new agent artifacts ════════════════════
    sql.append("-- ═══ STEP 6: Create 15 new agent artifacts ═══")
    sql.append("")
    for agent_name, agent_id in NEW_AGENTS.items():
        _emit_new_agent(sql, agent_name, agent_id, tools_res_id)

    # ═══ STEP 7: Update prompts & instructions for existing agents ═
    sql.append("-- ═══ STEP 7: Update prompts & instructions for existing agents ═══")
    sql.append("")

    # Map existing agent display names to prompt file stems
    # Training is now "Chat" but its agent_id is TRAINING_AGENT_ID
    existing_crud_agents = {
        "Agent",
        "Auth",
        "Cohort",
        "Department",
        "Document",
        "Model",
        "Parameter",
        "Persona",
        "Profile",
        "Provider",
        "Rubric",
        "Scenario",
        "Setting",
        "Simulation",
        "Tool",
    }

    for agent_name in sorted(existing_crud_agents):
        if agent_name not in existing or agent_name not in PROMPT_FILE:
            continue
        info = existing[agent_name]
        stem = PROMPT_FILE[agent_name]
        sys_content = read_prompt(stem, "system")
        instr_content = read_prompt(stem, "instructions")

        if info["prompt_id"] and sys_content:
            sql.append(f"-- Update prompt for {agent_name}")
            sql.append(
                f"UPDATE prompts_resource SET system_prompt = {dollar_quote(sys_content)}"
            )
            sql.append(f"WHERE id = '{info['prompt_id']}';")
            sql.append("")

        if info["instruction_ids"] and instr_content:
            sql.append(f"-- Update instruction for {agent_name}")
            sql.append(
                f"UPDATE instructions_resource SET template = {dollar_quote(instr_content)}"
            )
            sql.append(f"WHERE id = '{info['instruction_ids'][0]}';")
            sql.append("")

    # Handle Training/Chat (renamed) — needs prompt+instruction created if missing
    _emit_update_or_create_prompt(
        sql, "Chat", TRAINING_AGENT_ID, existing.get("Training", {}), tools_res_id
    )

    # Handle Benchmark — needs prompt+instruction created if missing
    _emit_update_or_create_prompt(
        sql,
        "Benchmark",
        existing.get("Benchmark", {}).get("agent_id", ""),
        existing.get("Benchmark", {}),
        tools_res_id,
    )

    # ═══ STEP 8: Update tool bindings for existing agents ═════════
    sql.append("-- ═══ STEP 8: Update tool bindings for existing agents ═══")
    sql.append("")

    # Map existing names to the name used in AGENT_TOOLS
    # Training → Chat in AGENT_TOOLS
    name_remap = {"Training": "Chat"}

    for db_name in sorted(existing_tools.keys()):
        tool_key = name_remap.get(db_name, db_name)
        if tool_key not in AGENT_TOOLS:
            continue
        expected = set(AGENT_TOOLS[tool_key])
        current = existing_tools.get(db_name, set())
        missing = expected - current
        if not missing:
            continue

        agent_id = existing[db_name]["agent_id"]
        sql.append(f"-- Add missing tools for {db_name}")
        for tool_name in sorted(missing):
            if tool_name not in tools_res_id:
                sql.append(f"-- SKIP {tool_name} (not found in DB)")
                continue
            tid = tools_res_id[tool_name]
            sql.append(
                f"INSERT INTO agent_tools_junction (agent_id, tool_id) "
                f"VALUES ('{agent_id}', '{tid}') ON CONFLICT DO NOTHING;"
            )
        sql.append("")

        # Also update agents_resource.tool_ids if the agent has one
        agents_res = existing[db_name].get("agents_resource_id")
        if agents_res:
            tool_ids_array = _tool_ids_array(AGENT_TOOLS[tool_key], tools_res_id)
            sql.append(f"UPDATE agents_resource SET tool_ids = {tool_ids_array}")
            sql.append(f"WHERE id = '{agents_res}';")
            sql.append("")

    # ═══ STEP 9: Wire all agents to settings ══════════════════════
    sql.append("-- ═══ STEP 9: Wire new agents to both settings ═══")
    sql.append("")
    sql.append("""DO $$
DECLARE
    v_agents_id uuid;
    v_setting_id uuid;
BEGIN
    -- Wire new agents (their agents_resource was created in step 6)
    FOR v_agents_id IN
        SELECT aaj.agents_id
        FROM agent_agents_junction aaj
        WHERE aaj.agent_id IN (""")
    agent_ids_list = ", ".join(f"'{aid}'" for aid in NEW_AGENTS.values())
    sql.append(f"            {agent_ids_list}")
    sql.append("""        )
    LOOP
        FOR v_setting_id IN SELECT unnest(ARRAY[""")
    settings_list = ", ".join(f"'{s}'::uuid" for s in SETTINGS)
    sql.append(f"            {settings_list}")
    sql.append("""        ]) LOOP
            INSERT INTO setting_agents_junction (setting_id, agents_id)
            VALUES (v_setting_id, v_agents_id)
            ON CONFLICT DO NOTHING;
        END LOOP;
    END LOOP;

    -- Also wire fixed Eval and Field agents' new agents_resource
    FOR v_agents_id IN
        SELECT aaj.agents_id
        FROM agent_agents_junction aaj""")
    sql.append(f"        WHERE aaj.agent_id IN ('{EVAL_AGENT_ID}', '{FIELD_AGENT_ID}')")
    sql.append("""    LOOP
        FOR v_setting_id IN SELECT unnest(ARRAY[""")
    sql.append(f"            {settings_list}")
    sql.append("""        ]) LOOP
            INSERT INTO setting_agents_junction (setting_id, agents_id)
            VALUES (v_setting_id, v_agents_id)
            ON CONFLICT DO NOTHING;
        END LOOP;
    END LOOP;
END $$;""")
    sql.append("")

    sql.append("COMMIT;")
    sql.append("")

    # Write output
    OUTPUT.write_text("\n".join(sql))
    print(f"Migration written to {OUTPUT}")
    print(f"Total lines: {len(sql)}")


# ─── SQL Generation Helpers ──────────────────────────────────────────────────


def _tool_ids_array(tool_names: list[str], tools_res_id: dict[str, str]) -> str:
    """Build a ARRAY[...]::uuid[] literal from tool names."""
    ids = []
    for t in tool_names:
        if t in tools_res_id:
            ids.append(f"'{tools_res_id[t]}'")
    if not ids:
        return "ARRAY[]::uuid[]"
    return "ARRAY[" + ", ".join(ids) + "]::uuid[]"


def _emit_fix_agent(
    sql: list[str],
    agent_name: str,
    agent_id: str,
    existing: dict[str, dict],
    tools_res_id: dict[str, str],
):
    """Emit SQL to fix an agent that shares resources with another agent.
    Creates new prompts_resource, instructions_resource, agents_resource,
    and updates all junctions.
    """
    stem = PROMPT_FILE[agent_name]
    sys_content = read_prompt(stem, "system")
    instr_content = read_prompt(stem, "instructions")
    desc = AGENT_DESC[agent_name]
    tool_names = AGENT_TOOLS[agent_name]
    tool_ids_arr = _tool_ids_array(tool_names, tools_res_id)

    info = existing.get(agent_name, {})
    old_agents_res = info.get("agents_resource_id")

    sql.append("")
    sql.append("DO $$")
    sql.append("DECLARE")
    sql.append("    v_prompt_id uuid;")
    sql.append("    v_instruction_id uuid;")
    sql.append("    v_agents_res_id uuid;")
    sql.append("BEGIN")

    # Create new prompt
    sql.append("    INSERT INTO prompts_resource (system_prompt, name, description)")
    sql.append(
        f"    VALUES ({dollar_quote(sys_content)}, {sql_literal(agent_name + ' Prompt')}, {sql_literal(desc)})"
    )
    sql.append("    RETURNING id INTO v_prompt_id;")
    sql.append("")

    # Create new instruction
    sql.append("    INSERT INTO instructions_resource (template)")
    sql.append(f"    VALUES ({dollar_quote(instr_content)})")
    sql.append("    RETURNING id INTO v_instruction_id;")
    sql.append("")

    # Create new agents_resource
    sql.append(
        "    INSERT INTO agents_resource (model_id, prompt_id, tool_ids, instruction_ids, department_ids)"
    )
    sql.append("    VALUES (")
    sql.append(f"        '{GPT41_MODEL_ID}',")
    sql.append("        v_prompt_id,")
    sql.append(f"        {tool_ids_arr},")
    sql.append("        ARRAY[v_instruction_id]::uuid[],")
    sql.append("        ARRAY[]::uuid[]")
    sql.append("    ) RETURNING id INTO v_agents_res_id;")
    sql.append("")

    # Remove old junctions
    if old_agents_res:
        sql.append(
            f"    DELETE FROM agent_agents_junction WHERE agent_id = '{agent_id}';"
        )
    sql.append(f"    DELETE FROM agent_prompts_junction WHERE agent_id = '{agent_id}';")
    sql.append(
        f"    DELETE FROM agent_instructions_junction WHERE agent_id = '{agent_id}';"
    )
    sql.append(f"    DELETE FROM agent_tools_junction WHERE agent_id = '{agent_id}';")
    sql.append("")

    # Insert new junctions
    sql.append(
        f"    INSERT INTO agent_agents_junction (agent_id, agents_id) VALUES ('{agent_id}', v_agents_res_id);"
    )
    sql.append(
        f"    INSERT INTO agent_prompts_junction (agent_id, prompt_id) VALUES ('{agent_id}', v_prompt_id);"
    )
    sql.append(
        f"    INSERT INTO agent_instructions_junction (agent_id, instruction_id) VALUES ('{agent_id}', v_instruction_id);"
    )
    sql.append("")

    # Insert tool junctions
    for t in tool_names:
        if t in tools_res_id:
            sql.append(
                f"    INSERT INTO agent_tools_junction (agent_id, tool_id) VALUES ('{agent_id}', '{tools_res_id[t]}') ON CONFLICT DO NOTHING;"
            )
    sql.append("")

    # Remove old agents_resource from settings (if it was shared)
    # and add new one
    if old_agents_res:
        sql.append(
            "    -- Remove old shared agents_resource from settings for this agent"
        )
        sql.append("    -- (Keep it for the other agent that shares it)")
    for s in SETTINGS:
        sql.append(
            f"    INSERT INTO setting_agents_junction (setting_id, agents_id) VALUES ('{s}', v_agents_res_id) ON CONFLICT DO NOTHING;"
        )

    sql.append("END $$;")
    sql.append("")


def _emit_new_agent(
    sql: list[str],
    agent_name: str,
    agent_id: str,
    tools_res_id: dict[str, str],
):
    """Emit SQL to create a completely new agent artifact with all resources."""
    stem = PROMPT_FILE[agent_name]
    sys_content = read_prompt(stem, "system")
    instr_content = read_prompt(stem, "instructions")
    desc = AGENT_DESC[agent_name]
    tool_names = AGENT_TOOLS[agent_name]
    tool_ids_arr = _tool_ids_array(tool_names, tools_res_id)

    sql.append(f"-- ── New Agent: {agent_name} ──")
    sql.append("DO $$")
    sql.append("DECLARE")
    sql.append("    v_prompt_id uuid;")
    sql.append("    v_instruction_id uuid;")
    sql.append("    v_agents_res_id uuid;")
    sql.append("    v_name_id uuid;")
    sql.append("    v_desc_id uuid;")
    sql.append("BEGIN")

    # Create prompt
    if sys_content:
        sql.append(
            "    INSERT INTO prompts_resource (system_prompt, name, description)"
        )
        sql.append(
            f"    VALUES ({dollar_quote(sys_content)}, {sql_literal(agent_name + ' Prompt')}, {sql_literal(desc)})"
        )
        sql.append("    RETURNING id INTO v_prompt_id;")
    else:
        sql.append("    v_prompt_id := NULL;")
    sql.append("")

    # Create instruction
    if instr_content:
        sql.append("    INSERT INTO instructions_resource (template)")
        sql.append(f"    VALUES ({dollar_quote(instr_content)})")
        sql.append("    RETURNING id INTO v_instruction_id;")
    else:
        sql.append("    v_instruction_id := NULL;")
    sql.append("")

    # Create agents_resource
    instr_arr = (
        "ARRAY[v_instruction_id]::uuid[]" if instr_content else "ARRAY[]::uuid[]"
    )
    sql.append(
        "    INSERT INTO agents_resource (model_id, prompt_id, tool_ids, instruction_ids, department_ids)"
    )
    sql.append("    VALUES (")
    sql.append(f"        '{GPT41_MODEL_ID}',")
    sql.append("        v_prompt_id,")
    sql.append(f"        {tool_ids_arr},")
    sql.append(f"        {instr_arr},")
    sql.append("        ARRAY[]::uuid[]")
    sql.append("    ) RETURNING id INTO v_agents_res_id;")
    sql.append("")

    # Create name (reuse if exists due to unique constraint)
    sql.append(
        f"    SELECT id INTO v_name_id FROM names_resource WHERE name = {sql_literal(agent_name)} LIMIT 1;"
    )
    sql.append("    IF v_name_id IS NULL THEN")
    sql.append(
        f"        INSERT INTO names_resource (name) VALUES ({sql_literal(agent_name)}) RETURNING id INTO v_name_id;"
    )
    sql.append("    END IF;")
    sql.append("")

    # Create description
    sql.append(
        f"    INSERT INTO descriptions_resource (description) VALUES ({sql_literal(desc)}) RETURNING id INTO v_desc_id;"
    )
    sql.append("")

    # Create artifact
    sql.append(f"    INSERT INTO agent_artifact (id) VALUES ('{agent_id}');")
    sql.append("")

    # Create junctions
    sql.append(
        f"    INSERT INTO agent_agents_junction (agent_id, agents_id) VALUES ('{agent_id}', v_agents_res_id);"
    )
    sql.append(
        f"    INSERT INTO agent_names_junction (agent_id, name_id) VALUES ('{agent_id}', v_name_id);"
    )
    sql.append(
        f"    INSERT INTO agent_descriptions_junction (agent_id, description_id) VALUES ('{agent_id}', v_desc_id);"
    )
    sql.append(
        f"    INSERT INTO agent_flags_junction (agent_id, flag_id, value) VALUES ('{agent_id}', '{AGENT_ACTIVE_FLAG}', true);"
    )
    sql.append(
        f"    INSERT INTO agent_models_junction (agent_id, model_id) VALUES ('{agent_id}', '{GPT41_MODEL_ID}');"
    )

    if sys_content:
        sql.append(
            f"    INSERT INTO agent_prompts_junction (agent_id, prompt_id) VALUES ('{agent_id}', v_prompt_id);"
        )
    if instr_content:
        sql.append(
            f"    INSERT INTO agent_instructions_junction (agent_id, instruction_id) VALUES ('{agent_id}', v_instruction_id);"
        )
    sql.append("")

    # Tool junctions
    for t in tool_names:
        if t in tools_res_id:
            sql.append(
                f"    INSERT INTO agent_tools_junction (agent_id, tool_id) VALUES ('{agent_id}', '{tools_res_id[t]}');"
            )
    sql.append("")

    sql.append("END $$;")
    sql.append("")


def _emit_update_or_create_prompt(
    sql: list[str],
    agent_name: str,
    agent_id: str,
    info: dict,
    tools_res_id: dict[str, str],
):
    """For agents that may or may not have prompts — update if exists, create if not."""
    stem = PROMPT_FILE.get(agent_name)
    if not stem:
        return
    sys_content = read_prompt(stem, "system")
    instr_content = read_prompt(stem, "instructions")
    if not sys_content and not instr_content:
        return

    desc = AGENT_DESC.get(agent_name, agent_name)

    if info.get("prompt_id") and sys_content:
        # Update existing prompt
        sql.append(f"-- Update prompt for {agent_name}")
        sql.append(
            f"UPDATE prompts_resource SET system_prompt = {dollar_quote(sys_content)}"
        )
        sql.append(f"WHERE id = '{info['prompt_id']}';")
        sql.append("")
    elif sys_content and not info.get("prompt_id"):
        # Create new prompt and junction
        sql.append(f"-- Create prompt for {agent_name} (had none)")
        sql.append("DO $$")
        sql.append("DECLARE v_prompt_id uuid;")
        sql.append("BEGIN")
        sql.append(
            "    INSERT INTO prompts_resource (system_prompt, name, description)"
        )
        sql.append(
            f"    VALUES ({dollar_quote(sys_content)}, {sql_literal(agent_name + ' Prompt')}, {sql_literal(desc)})"
        )
        sql.append("    RETURNING id INTO v_prompt_id;")
        sql.append(
            f"    INSERT INTO agent_prompts_junction (agent_id, prompt_id) VALUES ('{agent_id}', v_prompt_id);"
        )
        # Also set on agents_resource
        agents_res = info.get("agents_resource_id")
        if agents_res:
            sql.append(
                f"    UPDATE agents_resource SET prompt_id = v_prompt_id WHERE id = '{agents_res}';"
            )
        sql.append("END $$;")
        sql.append("")

    if info.get("instruction_ids") and instr_content:
        sql.append(f"-- Update instruction for {agent_name}")
        sql.append(
            f"UPDATE instructions_resource SET template = {dollar_quote(instr_content)}"
        )
        sql.append(f"WHERE id = '{info['instruction_ids'][0]}';")
        sql.append("")
    elif instr_content and not info.get("instruction_ids"):
        sql.append(f"-- Create instruction for {agent_name} (had none)")
        sql.append("DO $$")
        sql.append("DECLARE v_instr_id uuid;")
        sql.append("BEGIN")
        sql.append("    INSERT INTO instructions_resource (template)")
        sql.append(f"    VALUES ({dollar_quote(instr_content)})")
        sql.append("    RETURNING id INTO v_instr_id;")
        sql.append(
            f"    INSERT INTO agent_instructions_junction (agent_id, instruction_id) VALUES ('{agent_id}', v_instr_id);"
        )
        agents_res = info.get("agents_resource_id")
        if agents_res:
            sql.append(
                f"    UPDATE agents_resource SET instruction_ids = ARRAY[v_instr_id]::uuid[] WHERE id = '{agents_res}';"
            )
        sql.append("END $$;")
        sql.append("")


if __name__ == "__main__":
    main()
