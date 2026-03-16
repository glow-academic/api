"""Non-derivable business logic for the registry.

Contains data that cannot be introspected from the database or filesystem:
- RESOURCE_OUTPUT_SCHEMAS: curated tool output contracts
- ARTIFACT_ROLES: which roles can edit each artifact
- VIEW_ENTRIES: view → entry_type mappings
- ARTIFACT_VIEWS: complex artifact → view mappings
- VIEW_RESOURCES: view → resource mappings
- ARTIFACTS_WITHOUT_SOCKET: artifacts that have save but no socket
- Naming exception tables for code generation
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Artifacts that are in SAVE_REGISTRY but have no socket events
# ---------------------------------------------------------------------------
ARTIFACTS_WITHOUT_SOCKET: frozenset[str] = frozenset({"auth", "simulation"})

# ---------------------------------------------------------------------------
# Entry table name → registry key (non-obvious mappings)
# ---------------------------------------------------------------------------
ENTRY_TABLE_TO_KEY: dict[str, str] = {
    "attempt_analysis_entry": "analyses",
    "attempt_content_entry": "contents",
    "attempt_feedback_entry": "feedbacks",
    "attempt_grade_entry": "grades",
    "attempt_highlight_entry": "highlights",
    "attempt_hint_entry": "hints",
    "attempt_improvement_entry": "improvements",
    "attempt_replacement_entry": "replacements",
    "attempt_responses_entry": "attempt_responses",
    "attempt_strength_entry": "strengths",
}

# ---------------------------------------------------------------------------
# Section overrides (artifact → section when convention doesn't hold)
# ---------------------------------------------------------------------------
SECTION_OVERRIDES: dict[str, str] = {
    "setting": "settings",
}

# ---------------------------------------------------------------------------
# Route → artifact overrides (when client route name doesn't match artifact)
# ---------------------------------------------------------------------------
ROUTE_TO_ARTIFACT: dict[str, str] = {}

# ---------------------------------------------------------------------------
# View endpoint overrides (when convention doesn't hold)
# ---------------------------------------------------------------------------
VIEW_ENDPOINT_OVERRIDES: dict[str, frozenset[str]] = {
    "dashboard": frozenset({"get", "refresh", "docs"}),
    "reports": frozenset({"search", "export", "refresh", "docs"}),
    "activity": frozenset({"get", "problem", "refresh", "resolve", "docs"}),
    "attempt": frozenset({"get", "archive", "certifficate", "docs"}),
    "record": frozenset(),
    "invocation": frozenset({"get", "draft"}),
    "chat": frozenset({"get", "draft", "refresh", "docs"}),
}

# ---------------------------------------------------------------------------
# artifact_roles_relation (artifact_type → profile_type)
# No DB table — purely business logic
# ---------------------------------------------------------------------------
ARTIFACT_ROLES: dict[str, frozenset[str]] = {
    "agent": frozenset({"admin", "superadmin"}),
    "auth": frozenset({"superadmin"}),
    "cohort": frozenset({"admin", "instructional", "superadmin"}),
    "department": frozenset({"superadmin"}),
    "document": frozenset({"admin", "superadmin"}),
    "eval": frozenset({"superadmin"}),
    "field": frozenset({"admin", "superadmin"}),
    "model": frozenset({"admin", "superadmin"}),
    "parameter": frozenset({"admin", "superadmin"}),
    "persona": frozenset({"admin", "instructional", "superadmin"}),
    "profile": frozenset({"admin", "superadmin"}),
    "provider": frozenset({"admin", "superadmin"}),
    "rubric": frozenset({"superadmin"}),
    "scenario": frozenset({"admin", "instructional", "superadmin"}),
    "setting": frozenset({"admin", "superadmin"}),
    "simulation": frozenset({"admin", "instructional", "superadmin"}),
    "tool": frozenset({"admin", "superadmin"}),
}

# ---------------------------------------------------------------------------
# view_entry_relation (view_type → entry_type)
# Only 2 entries — business logic
# ---------------------------------------------------------------------------
VIEW_ENTRIES: dict[str, frozenset[str]] = {
    "benchmark_messages": frozenset({"highlights", "messages", "replacements"}),
    "simulation_messages": frozenset({"highlights", "messages", "replacements"}),
}

# ---------------------------------------------------------------------------
# artifact_view_relation (artifact_type → view_type)
# Complex mapping with exceptions — not derivable
# ---------------------------------------------------------------------------
ARTIFACT_VIEWS: dict[str, frozenset[str]] = {
    "attempt": frozenset(
        {"simulation_attempts", "simulation_chats", "simulation_messages"}
    ),
    "benchmark": frozenset(
        {
            "benchmark_attempts",
            "benchmark_chats",
            "benchmark_history",
            "benchmark_messages",
            "benchmark_overview",
        }
    ),
    "chat": frozenset(
        {"simulation_attempts", "simulation_chats", "simulation_messages"}
    ),
    "dashboard": frozenset(
        {"simulation_history", "simulation_messages", "simulation_overview"}
    ),
    "home": frozenset(
        {
            "simulation_attempts",
            "simulation_chats",
            "simulation_history",
            "simulation_messages",
            "simulation_overview",
        }
    ),
    "leaderboard": frozenset({"simulation_messages", "simulation_overview"}),
    "practice": frozenset(
        {
            "simulation_attempts",
            "simulation_chats",
            "simulation_history",
            "simulation_messages",
            "simulation_overview",
        }
    ),
    "reports": frozenset(
        {
            "simulation_attempts",
            "simulation_chats",
            "simulation_history",
            "simulation_messages",
            "simulation_overview",
        }
    ),
    "test": frozenset({"benchmark_attempts", "benchmark_chats", "benchmark_messages"}),
}

# ---------------------------------------------------------------------------
# view_resource_relation (view_type → resource_type)
# 10 view → resource mappings — not derivable
# ---------------------------------------------------------------------------
VIEW_RESOURCES: dict[str, frozenset[str]] = {
    "benchmark_attempts": frozenset(
        {
            "cohorts",
            "departments",
            "profiles",
            "simulations",
        }
    ),
    "benchmark_chats": frozenset(
        {
            "personas",
            "profiles",
            "rubrics",
            "scenarios",
            "simulations",
        }
    ),
    "benchmark_history": frozenset(
        {
            "cohorts",
            "departments",
            "personas",
            "profiles",
            "scenarios",
            "simulations",
        }
    ),
    "benchmark_messages": frozenset(
        {
            "personas",
            "profiles",
            "scenarios",
            "simulations",
        }
    ),
    "benchmark_overview": frozenset(
        {
            "cohorts",
            "departments",
            "personas",
            "profiles",
            "rubrics",
            "simulations",
        }
    ),
    "simulation_attempts": frozenset(
        {
            "cohorts",
            "departments",
            "profiles",
            "simulations",
        }
    ),
    "simulation_chats": frozenset(
        {
            "documents",
            "images",
            "objectives",
            "options",
            "personas",
            "problem_statements",
            "profiles",
            "questions",
            "rubrics",
            "scenarios",
            "simulations",
            "standard_groups",
            "standards",
            "videos",
        }
    ),
    "simulation_history": frozenset(
        {
            "cohorts",
            "departments",
            "personas",
            "profiles",
            "scenarios",
            "simulations",
        }
    ),
    "simulation_messages": frozenset(
        {
            "personas",
            "profiles",
            "scenarios",
            "simulations",
        }
    ),
    "simulation_overview": frozenset(
        {
            "cohorts",
            "departments",
            "personas",
            "profiles",
            "rubrics",
            "simulations",
        }
    ),
}

# ---------------------------------------------------------------------------
# resource_outputs_relation (resource_type → output schema fields)
# Curated tool output contracts — not derivable from DB schema
# ---------------------------------------------------------------------------
RESOURCE_OUTPUT_SCHEMAS: dict[str, list[dict[str, str]]] = {
    "agents": [{"field_type": "string", "name": "id"}],
    "arg_positions": [{"field_type": "string", "name": "id"}],
    "args": [{"field_type": "string", "name": "id"}],
    "args_outputs": [{"field_type": "string", "name": "id"}],
    "auth_item_keys": [{"field_type": "string", "name": "id"}],
    "cohorts": [{"field_type": "string", "name": "id"}],
    "colors": [
        {"field_type": "string", "name": "description"},
        {"field_type": "string", "name": "hex_code"},
        {"field_type": "string", "name": "id"},
        {"field_type": "string", "name": "name"},
    ],
    "departments": [{"field_type": "string", "name": "id"}],
    "descriptions": [
        {"field_type": "string", "name": "description"},
        {"field_type": "string", "name": "id"},
    ],
    "documents": [{"field_type": "string", "name": "id"}],
    "emails": [{"field_type": "string", "name": "email"}],
    "endpoints": [{"field_type": "string", "name": "base_url"}],
    "evals": [{"field_type": "string", "name": "id"}],
    "examples": [
        {"field_type": "string", "name": "example"},
        {"field_type": "string", "name": "id"},
    ],
    "fields": [{"field_type": "string", "name": "id"}],
    "flags": [{"field_type": "string", "name": "id"}],
    "group_positions": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "eval_id"},
        {"field_type": "string", "name": "group_id"},
        {"field_type": "string", "name": "value"},
    ],
    "group_rubrics": [{"field_type": "string", "name": "id"}],
    "groups": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "group_id"},
    ],
    "icons": [{"field_type": "string", "name": "id"}],
    "images": [
        {"field_type": "string", "name": "description"},
        {"field_type": "string", "name": "name"},
    ],
    "instructions": [
        {"field_type": "string", "name": "id"},
        {"field_type": "string", "name": "template"},
    ],
    "items": [
        {"field_type": "string", "name": "description"},
        {"field_type": "boolean", "name": "encrypted"},
        {"field_type": "string", "name": "name"},
        {"field_type": "number", "name": "position"},
    ],
    "keys": [
        {"field_type": "string", "name": "id"},
        {"field_type": "string", "name": "key_id"},
    ],
    "modalities": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "modality"},
    ],
    "models": [
        {"field_type": "string", "name": "id"},
        {"field_type": "string", "name": "value"},
    ],
    "names": [
        {"field_type": "string", "name": "id"},
        {"field_type": "string", "name": "name"},
    ],
    "objectives": [{"field_type": "string", "name": "objective"}],
    "options": [
        {"field_type": "boolean", "name": "is_correct"},
        {"field_type": "string", "name": "option_text"},
    ],
    "parameter_fields": [
        {"field_type": "string", "name": "field_id"},
        {"field_type": "string", "name": "id"},
        {"field_type": "string", "name": "parameter_id"},
    ],
    "parameters": [{"field_type": "string", "name": "id"}],
    "personas": [{"field_type": "string", "name": "id"}],
    "points": [{"field_type": "string", "name": "value"}],
    "pricing": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "number", "name": "price"},
        {"field_type": "string", "name": "pricing_type"},
        {"field_type": "string", "name": "unit_name"},
        {"field_type": "string", "name": "unit_category"},
        {"field_type": "number", "name": "unit_value"},
    ],
    "problem_statements": [
        {"field_type": "string", "name": "name"},
        {"field_type": "string", "name": "problem_statement"},
    ],
    "profiles": [{"field_type": "string", "name": "id"}],
    "prompts": [
        {"field_type": "string", "name": "description"},
        {"field_type": "string", "name": "name"},
        {"field_type": "string", "name": "system_prompt"},
    ],
    "protocols": [{"field_type": "string", "name": "value"}],
    "provider_keys": [{"field_type": "string", "name": "id"}],
    "providers": [{"field_type": "string", "name": "provider_id"}],
    "qualities": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "quality"},
    ],
    "questions": [
        {"field_type": "boolean", "name": "allow_multiple"},
        {"field_type": "string", "name": "question_text"},
        {"field_type": "number", "name": "time"},
    ],
    "reasoning_levels": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "reasoning_level"},
        {"field_type": "string", "name": "reasoning_level_id"},
    ],
    "request_limits": [{"field_type": "number", "name": "requests_per_day"}],
    "rubrics": [{"field_type": "string", "name": "id"}],
    "run_positions": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "eval_id"},
        {"field_type": "string", "name": "run_id"},
        {"field_type": "string", "name": "value"},
    ],
    "run_rubrics": [{"field_type": "string", "name": "id"}],
    "runs": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "run_id"},
    ],
    "scenario_flags": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "description"},
        {"field_type": "string", "name": "icon_id"},
        {"field_type": "string", "name": "id"},
        {"field_type": "string", "name": "name"},
    ],
    "scenario_positions": [
        {"field_type": "string", "name": "id"},
        {"field_type": "string", "name": "scenario_id"},
        {"field_type": "string", "name": "simulation_id"},
        {"field_type": "string", "name": "value"},
    ],
    "scenario_rubrics": [{"field_type": "string", "name": "id"}],
    "scenario_time_limits": [{"field_type": "string", "name": "id"}],
    "scenarios": [{"field_type": "string", "name": "id"}],
    "settings": [{"field_type": "string", "name": "id"}],
    "simulation_availability": [
        {"field_type": "string", "name": "simulation_id"},
        {"field_type": "number", "name": "time"},
        {"field_type": "string", "name": "type"},
    ],
    "simulation_positions": [
        {"field_type": "string", "name": "simulation_id"},
        {"field_type": "string", "name": "value"},
    ],
    "simulations": [{"field_type": "string", "name": "id"}],
    "slugs": [{"field_type": "string", "name": "value"}],
    "standard_groups": [
        {"field_type": "string", "name": "description"},
        {"field_type": "string", "name": "name"},
        {"field_type": "number", "name": "pass_points"},
        {"field_type": "number", "name": "points"},
        {"field_type": "string", "name": "short_name"},
    ],
    "temperature_levels": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "boolean", "name": "is_upper"},
        {"field_type": "number", "name": "temperature"},
        {"field_type": "string", "name": "temperature_level_id"},
    ],
    "texts": [{"field_type": "string", "name": "id"}],
    "thresholds": [{"field_type": "string", "name": "value"}],
    "uploads": [{"field_type": "string", "name": "id"}],
    "values": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "value"},
    ],
    "videos": [
        {"field_type": "string", "name": "description"},
        {"field_type": "number", "name": "length_seconds"},
        {"field_type": "string", "name": "name"},
    ],
    "voices": [
        {"field_type": "boolean", "name": "active"},
        {"field_type": "string", "name": "voice"},
        {"field_type": "string", "name": "voice_id"},
    ],
}
