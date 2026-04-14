"""Flat operation registry: (name, op) → (module, func) or None.

Each layer (artifacts, resources, entries, infra) has a dict mapping
``(name, operation)`` to either a ``(module_path, function_name)`` tuple
or ``None`` when the operation is not yet implemented.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any


# ---------------------------------------------------------------------------
# Operation classification: READ vs WRITE
#
# WRITE operations mutate state and need ack during generation (soft path).
# READ operations are safe to execute immediately.
# ---------------------------------------------------------------------------

WRITE_OPERATIONS: frozenset[str] = frozenset({
    # CRUD
    "create", "update", "delete", "duplicate", "draft", "refresh",
    # Uploads
    "image_upload", "video_upload", "text_upload", "file_upload", "audio_upload",
    # Artifact-specific
    "run", "generate", "problem", "resolve", "emulate", "unemulate",
    "context", "name", "group", "feedback",
    # State machine
    "start", "next", "end", "end_all", "message", "grade", "stop",
    "response", "previous", "archive",
    "audio_start", "audio_frame", "audio_stop", "audio_mute",
})


def is_write_operation(operation: str) -> bool:
    """Check if an operation mutates state (needs ack during generation)."""
    return operation in WRITE_OPERATIONS


def resolve_callable(
    name: str,
    operation: str,
    ops: dict[tuple[str, str], tuple[str, str] | None],
) -> Callable[..., Any] | None:
    """Look up (name, operation) in an OPS dict and return the imported callable.

    Returns ``None`` if the entry is missing or maps to ``None`` (unimplemented).
    """
    entry = ops.get((name, operation))
    if entry is None:
        return None
    module_path, func_name = entry
    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Artifact operations: (artifact_name, op) → (module_path, function_name) | None
#
# Standard CRUD artifacts have all 7 ops.  View-only artifacts typically
# only have "get".  Unimplemented ops map to None.
#
# Naming conventions (actual, confirmed by exploration):
#   get       → get_{name}_websocket        (exception: benchmark → get_benchmark)
#   list      → get_{name}_list
#   delete    → delete_{name}
#   duplicate → duplicate_{name}
#   draft     → patch_{name}_draft
#   docs      → None (not yet implemented)
# ---------------------------------------------------------------------------

_A = "app.routes"

ARTIFACT_OPS: dict[tuple[str, str], tuple[str, str] | None] = {
    # activity (view-only)
    ("activity", "get"): (f"{_A}.activity.get", "get_activity_websocket"),
    ("activity", "list"): None,
    ("activity", "save"): None,
    ("activity", "delete"): None,
    ("activity", "duplicate"): None,
    ("activity", "draft"): None,
    ("activity", "docs"): None,
    ("activity", "export"): None,
    ("activity", "refresh"): (f"{_A}.activity.refresh", "activity_refresh"),
    # agent
    ("agent", "get"): (f"{_A}.agent.get", "get_agent_websocket"),
    ("agent", "list"): (f"{_A}.agent.list", "get_agent_list"),
    ("agent", "save"): None,
    ("agent", "delete"): (f"{_A}.agent.delete", "delete_agent"),
    ("agent", "duplicate"): (f"{_A}.agent.duplicate", "duplicate_agent"),
    ("agent", "draft"): (f"{_A}.agent.draft", "patch_agent_draft"),
    ("agent", "docs"): None,
    ("agent", "export"): None,
    ("agent", "refresh"): None,
    # attempt (view-only)
    ("attempt", "get"): (f"{_A}.attempt.get", "get_attempt_websocket"),
    ("attempt", "list"): None,
    ("attempt", "save"): None,
    ("attempt", "delete"): None,
    ("attempt", "duplicate"): None,
    ("attempt", "draft"): None,
    ("attempt", "docs"): None,
    ("attempt", "export"): None,
    ("attempt", "refresh"): None,
    # auth
    ("auth", "get"): (f"{_A}.auth.get", "get_auth_websocket"),
    ("auth", "list"): (f"{_A}.auth.list", "get_auth_list"),
    ("auth", "save"): None,
    ("auth", "delete"): (f"{_A}.auth.delete", "delete_auth"),
    ("auth", "duplicate"): (f"{_A}.auth.duplicate", "duplicate_auth"),
    ("auth", "draft"): (f"{_A}.auth.draft", "patch_auth_draft"),
    ("auth", "docs"): None,
    ("auth", "export"): None,
    ("auth", "refresh"): None,
    # benchmark (view-only, no websocket)
    ("benchmark", "get"): (f"{_A}.benchmark.get", "get_benchmark"),
    ("benchmark", "list"): None,
    ("benchmark", "save"): None,
    ("benchmark", "delete"): None,
    ("benchmark", "duplicate"): None,
    ("benchmark", "draft"): None,
    ("benchmark", "docs"): None,
    ("benchmark", "export"): None,
    ("benchmark", "refresh"): (f"{_A}.benchmark.refresh", "benchmark_refresh"),
    # chat (partial — has get, save, draft)
    ("chat", "get"): (f"{_A}.chat.get", "get_chat_websocket"),
    ("chat", "list"): None,
    ("chat", "save"): None,
    ("chat", "delete"): None,
    ("chat", "duplicate"): None,
    ("chat", "draft"): (f"{_A}.chat.draft", "patch_chat_draft"),
    ("chat", "docs"): None,
    ("chat", "export"): None,
    ("chat", "refresh"): (f"{_A}.chat.refresh", "chat_refresh"),
    # cohort
    ("cohort", "get"): (f"{_A}.cohort.get", "get_cohort_websocket"),
    ("cohort", "list"): (f"{_A}.cohort.list", "get_cohort_list"),
    ("cohort", "save"): None,
    ("cohort", "delete"): (f"{_A}.cohort.delete", "delete_cohort"),
    ("cohort", "duplicate"): (f"{_A}.cohort.duplicate", "duplicate_cohort"),
    ("cohort", "draft"): (f"{_A}.cohort.draft", "patch_cohort_draft"),
    ("cohort", "docs"): None,
    ("cohort", "export"): (f"{_A}.cohort.export", "export_cohorts"),
    ("cohort", "refresh"): None,
    # dashboard (view-only)
    ("dashboard", "get"): (f"{_A}.dashboard.get", "get_dashboard_websocket"),
    ("dashboard", "list"): None,
    ("dashboard", "save"): None,
    ("dashboard", "delete"): None,
    ("dashboard", "duplicate"): None,
    ("dashboard", "draft"): None,
    ("dashboard", "docs"): None,
    ("dashboard", "export"): (f"{_A}.dashboard.export", "export_dashboard"),
    ("dashboard", "refresh"): (f"{_A}.dashboard.refresh", "dashboard_refresh"),
    # department
    ("department", "get"): (f"{_A}.department.get", "get_department_websocket"),
    ("department", "list"): (f"{_A}.department.list", "get_department_list"),
    ("department", "save"): None,
    ("department", "delete"): (f"{_A}.department.delete", "delete_department"),
    ("department", "duplicate"): (f"{_A}.department.duplicate", "duplicate_department"),
    ("department", "draft"): (f"{_A}.department.draft", "patch_department_draft"),
    ("department", "docs"): None,
    ("department", "export"): None,
    ("department", "refresh"): None,
    # document
    ("document", "get"): (f"{_A}.document.get", "get_document_websocket"),
    ("document", "list"): (f"{_A}.document.list", "get_document_list"),
    ("document", "save"): None,
    ("document", "delete"): (f"{_A}.document.delete", "delete_document"),
    ("document", "duplicate"): (f"{_A}.document.duplicate", "duplicate_document"),
    ("document", "draft"): (f"{_A}.document.draft", "patch_document_draft"),
    ("document", "docs"): None,
    ("document", "export"): None,
    ("document", "refresh"): None,
    # eval
    ("eval", "get"): (f"{_A}.eval.get", "get_eval_websocket"),
    ("eval", "list"): (f"{_A}.eval.list", "get_eval_list"),
    ("eval", "save"): None,
    ("eval", "delete"): (f"{_A}.eval.delete", "delete_eval"),
    ("eval", "duplicate"): (f"{_A}.eval.duplicate", "duplicate_eval"),
    ("eval", "draft"): (f"{_A}.eval.draft", "patch_eval_draft"),
    ("eval", "docs"): None,
    ("eval", "export"): None,
    ("eval", "refresh"): None,
    # field
    ("field", "get"): (f"{_A}.field.get", "get_field_websocket"),
    ("field", "list"): (f"{_A}.field.list", "get_field_list"),
    ("field", "save"): None,
    ("field", "delete"): (f"{_A}.field.delete", "delete_field"),
    ("field", "duplicate"): (f"{_A}.field.duplicate", "duplicate_field"),
    ("field", "draft"): (f"{_A}.field.draft", "patch_field_draft"),
    ("field", "docs"): None,
    ("field", "export"): None,
    ("field", "refresh"): None,
    # group (view-only)
    ("group", "get"): None,
    ("group", "list"): None,
    ("group", "save"): None,
    ("group", "delete"): None,
    ("group", "duplicate"): None,
    ("group", "draft"): None,
    ("group", "docs"): None,
    ("group", "export"): None,
    ("group", "refresh"): None,
    # health (view-only)
    ("health", "get"): None,
    ("health", "list"): None,
    ("health", "save"): None,
    ("health", "delete"): None,
    ("health", "duplicate"): None,
    ("health", "draft"): None,
    ("health", "docs"): None,
    ("health", "export"): None,
    ("health", "refresh"): (f"{_A}.health.refresh", "health_refresh"),
    # home (view-only)
    ("home", "get"): (f"{_A}.home.get", "get_home_websocket"),
    ("home", "list"): None,
    ("home", "save"): None,
    ("home", "delete"): None,
    ("home", "duplicate"): None,
    ("home", "draft"): None,
    ("home", "docs"): None,
    ("home", "export"): (f"{_A}.home.export", "export_home"),
    ("home", "refresh"): None,
    # invocation (view-only + draft)
    ("invocation", "get"): (f"{_A}.invocation.get", "get_invocation_websocket"),
    ("invocation", "list"): None,
    ("invocation", "save"): None,
    ("invocation", "delete"): None,
    ("invocation", "duplicate"): None,
    ("invocation", "draft"): (f"{_A}.invocation.draft", "patch_invocation_draft"),
    ("invocation", "docs"): None,
    ("invocation", "export"): None,
    ("invocation", "refresh"): None,
    # leaderboard (view-only)
    ("leaderboard", "get"): (f"{_A}.leaderboard.get", "get_leaderboard_websocket"),
    ("leaderboard", "list"): None,
    ("leaderboard", "save"): None,
    ("leaderboard", "delete"): None,
    ("leaderboard", "duplicate"): None,
    ("leaderboard", "draft"): None,
    ("leaderboard", "docs"): None,
    ("leaderboard", "export"): (f"{_A}.leaderboard.export", "export_leaderboard"),
    ("leaderboard", "refresh"): (f"{_A}.leaderboard.refresh", "leaderboard_refresh"),
    # model
    ("model", "get"): (f"{_A}.model.get", "get_model_websocket"),
    ("model", "list"): (f"{_A}.model.list", "get_model_list"),
    ("model", "save"): None,
    ("model", "delete"): (f"{_A}.model.delete", "delete_model"),
    ("model", "duplicate"): (f"{_A}.model.duplicate", "duplicate_model"),
    ("model", "draft"): (f"{_A}.model.draft", "patch_model_draft"),
    ("model", "docs"): None,
    ("model", "export"): None,
    ("model", "refresh"): None,
    # parameter
    ("parameter", "get"): (f"{_A}.parameter.get", "get_parameter_websocket"),
    ("parameter", "list"): (f"{_A}.parameter.list", "get_parameter_list"),
    ("parameter", "save"): None,
    ("parameter", "delete"): (f"{_A}.parameter.delete", "delete_parameter"),
    ("parameter", "duplicate"): (f"{_A}.parameter.duplicate", "duplicate_parameter"),
    ("parameter", "draft"): (f"{_A}.parameter.draft", "patch_parameter_draft"),
    ("parameter", "docs"): None,
    ("parameter", "export"): None,
    ("parameter", "refresh"): None,
    # persona
    ("persona", "get"): (f"{_A}.persona.get", "get_persona_websocket"),
    ("persona", "list"): (f"{_A}.persona.list", "get_persona_list"),
    ("persona", "save"): None,
    ("persona", "delete"): (f"{_A}.persona.delete", "delete_persona"),
    ("persona", "duplicate"): (f"{_A}.persona.duplicate", "duplicate_persona"),
    ("persona", "draft"): (f"{_A}.persona.draft", "patch_persona_draft"),
    ("persona", "docs"): None,
    ("persona", "export"): (f"{_A}.persona.export", "export_personas"),
    ("persona", "refresh"): None,
    # practice (view-only)
    ("practice", "get"): (f"{_A}.practice.get", "get_practice_websocket"),
    ("practice", "list"): None,
    ("practice", "save"): None,
    ("practice", "delete"): None,
    ("practice", "duplicate"): None,
    ("practice", "draft"): None,
    ("practice", "docs"): None,
    ("practice", "export"): (f"{_A}.practice.export", "export_practice"),
    ("practice", "refresh"): None,
    # pricing (view-only)
    ("pricing", "get"): (f"{_A}.pricing.get", "get_pricing_websocket"),
    ("pricing", "list"): None,
    ("pricing", "save"): None,
    ("pricing", "delete"): None,
    ("pricing", "duplicate"): None,
    ("pricing", "draft"): None,
    ("pricing", "docs"): None,
    ("pricing", "export"): (f"{_A}.pricing.export", "export_pricing"),
    ("pricing", "refresh"): (f"{_A}.pricing.refresh", "pricing_refresh"),
    # profile
    ("profile", "get"): (f"{_A}.profile.get", "get_profile_websocket"),
    ("profile", "list"): (f"{_A}.profile.list", "get_profile_list"),
    ("profile", "save"): None,
    ("profile", "delete"): (f"{_A}.profile.delete", "delete_profile"),
    ("profile", "duplicate"): (f"{_A}.profile.duplicate", "duplicate_profile"),
    ("profile", "draft"): (f"{_A}.profile.draft", "patch_profile_draft"),
    ("profile", "docs"): None,
    ("profile", "export"): None,
    ("profile", "refresh"): None,
    # provider
    ("provider", "get"): (f"{_A}.provider.get", "get_provider_websocket"),
    ("provider", "list"): (f"{_A}.provider.list", "get_provider_list"),
    ("provider", "save"): None,
    ("provider", "delete"): (f"{_A}.provider.delete", "delete_provider"),
    ("provider", "duplicate"): (f"{_A}.provider.duplicate", "duplicate_provider"),
    ("provider", "draft"): (f"{_A}.provider.draft", "patch_provider_draft"),
    ("provider", "docs"): None,
    ("provider", "export"): None,
    ("provider", "refresh"): None,
    # record (view-only)
    ("record", "get"): None,
    ("record", "list"): None,
    ("record", "save"): None,
    ("record", "delete"): None,
    ("record", "duplicate"): None,
    ("record", "draft"): None,
    ("record", "docs"): None,
    ("record", "export"): None,
    ("record", "refresh"): None,
    # reports (view-only)
    ("reports", "search"): (f"{_A}.reports.search", "get_reports"),
    ("reports", "list"): None,
    ("reports", "save"): None,
    ("reports", "delete"): None,
    ("reports", "duplicate"): None,
    ("reports", "draft"): None,
    ("reports", "docs"): None,
    ("reports", "export"): (f"{_A}.reports.export", "export_report"),
    ("reports", "refresh"): (f"{_A}.reports.refresh", "reports_refresh"),
    # rubric
    ("rubric", "get"): (f"{_A}.rubric.get", "get_rubric_websocket"),
    ("rubric", "list"): (f"{_A}.rubric.list", "get_rubric_list"),
    ("rubric", "save"): None,
    ("rubric", "delete"): (f"{_A}.rubric.delete", "delete_rubric"),
    ("rubric", "duplicate"): (f"{_A}.rubric.duplicate", "duplicate_rubric"),
    ("rubric", "draft"): (f"{_A}.rubric.draft", "patch_rubric_draft"),
    ("rubric", "docs"): None,
    ("rubric", "export"): None,
    ("rubric", "refresh"): None,
    # scenario
    ("scenario", "get"): (f"{_A}.scenario.get", "get_scenario_websocket"),
    ("scenario", "list"): (f"{_A}.scenario.list", "get_scenario_list"),
    ("scenario", "save"): None,
    ("scenario", "delete"): (f"{_A}.scenario.delete", "delete_scenario"),
    ("scenario", "duplicate"): (f"{_A}.scenario.duplicate", "duplicate_scenario"),
    ("scenario", "draft"): (f"{_A}.scenario.draft", "patch_scenario_draft"),
    ("scenario", "docs"): None,
    ("scenario", "export"): (f"{_A}.scenario.export", "export_scenarios"),
    ("scenario", "refresh"): None,
    # session (view-only)
    ("session", "get"): None,
    ("session", "list"): None,
    ("session", "save"): None,
    ("session", "delete"): None,
    ("session", "duplicate"): None,
    ("session", "draft"): None,
    ("session", "docs"): None,
    ("session", "export"): None,
    ("session", "refresh"): None,
    # setting
    ("setting", "get"): (f"{_A}.setting.get", "get_setting_websocket"),
    ("setting", "list"): (f"{_A}.setting.list", "get_setting_list"),
    ("setting", "save"): None,
    ("setting", "delete"): (f"{_A}.setting.delete", "delete_setting"),
    ("setting", "duplicate"): (f"{_A}.setting.duplicate", "duplicate_setting"),
    ("setting", "draft"): (f"{_A}.setting.draft", "patch_setting_draft"),
    ("setting", "docs"): None,
    ("setting", "export"): None,
    ("setting", "refresh"): None,
    # simulation
    ("simulation", "get"): (f"{_A}.simulation.get", "get_simulation_websocket"),
    ("simulation", "list"): (f"{_A}.simulation.list", "get_simulation_list"),
    ("simulation", "save"): None,
    ("simulation", "delete"): (f"{_A}.simulation.delete", "delete_simulation"),
    ("simulation", "duplicate"): (f"{_A}.simulation.duplicate", "duplicate_simulation"),
    ("simulation", "draft"): (f"{_A}.simulation.draft", "patch_simulation_draft"),
    ("simulation", "docs"): None,
    ("simulation", "export"): (f"{_A}.simulation.export", "export_simulations"),
    ("simulation", "refresh"): None,
    # test (view-only)
    ("test", "get"): (f"{_A}.test.get", "get_test_websocket"),
    ("test", "list"): None,
    ("test", "save"): None,
    ("test", "delete"): None,
    ("test", "duplicate"): None,
    ("test", "draft"): None,
    ("test", "docs"): None,
    ("test", "export"): None,
    ("test", "refresh"): None,
    # tool
    ("tool", "get"): (f"{_A}.tool.get", "get_tool_websocket"),
    ("tool", "list"): (f"{_A}.tool.list", "get_tool_list"),
    ("tool", "save"): None,
    ("tool", "delete"): (f"{_A}.tool.delete", "delete_tool"),
    ("tool", "duplicate"): (f"{_A}.tool.duplicate", "duplicate_tool"),
    ("tool", "draft"): (f"{_A}.tool.draft", "patch_tool_draft"),
    ("tool", "docs"): None,
    ("tool", "export"): None,
    ("tool", "refresh"): None,
}

# ---------------------------------------------------------------------------
# Resource operations: (resource_name, op) → (module_path, function_name) | None
#
# Naming conventions (actual):
#   get    → get_{name}_internal
#   create → create_{name}_internal
#   link   → link_{name}_internal
#   search → search_{name}_internal
#   docs   → None (not yet implemented)
# ---------------------------------------------------------------------------

_R = "app.tools.resources"


def _res(
    name: str,
    *,
    get: bool = True,
    create: bool = False,
    link: bool = False,
    search: bool = False,
) -> dict[tuple[str, str], tuple[str, str] | None]:
    """Helper to generate resource op entries."""
    d: dict[tuple[str, str], tuple[str, str] | None] = {}
    d[(name, "get")] = (f"{_R}.{name}.get", f"get_{name}") if get else None
    d[(name, "create")] = (f"{_R}.{name}.create", f"create_{name}") if create else None
    d[(name, "link")] = (f"{_R}.{name}.link", f"link_{name}") if link else None
    d[(name, "search")] = (f"{_R}.{name}.search", f"search_{name}") if search else None
    d[(name, "docs")] = None
    return d


RESOURCE_OPS: dict[tuple[str, str], tuple[str, str] | None] = {
    **_res("agents", get=True, search=True),
    **_res("arg_positions", get=True, create=True, search=True),
    **_res("args", get=True, create=True, search=True),
    **_res("args_outputs", get=True, create=True, search=True),
    **_res("auth_item_keys", get=True, create=True, search=True),
    **_res("auths", get=True, search=True),
    **_res("cohorts", get=True, create=True, search=True),
    **_res("colors", get=True, create=True, link=True, search=True),
    **_res("conditional_parameters", get=True, search=True),
    **_res("departments", get=True, link=True, search=True),
    **_res("descriptions", get=True, create=True, link=True, search=True),
    **_res("documents", get=True, link=True, search=True),
    **_res("emails", get=True, create=True, search=True),
    **_res("endpoints", get=True, create=True, search=True),
    **_res("evals", get=True, search=True),
    **_res("examples", get=True, create=True, link=True, search=True),
    **_res("fields", get=True, link=True, search=True),
    **_res("flags", get=True, link=True, search=True),
    **_res("group_positions", get=True, create=True, search=True),
    **_res("group_rubrics", get=True, create=True, search=True),
    **_res("groups", get=True, search=True),
    **_res("icons", get=True, link=True, search=True),
    **_res("images", get=True, create=True, link=True, search=True),
    **_res("instructions", get=True, create=True, link=True, search=True),
    **_res("items", get=True, create=True, search=True),
    **_res("keys", get=True, create=True, search=True),
    **_res("modalities", get=True, search=True),
    **_res("models", get=True, search=True),
    **_res("names", get=True, create=True, link=True, search=True),
    **_res("objectives", get=True, create=True, link=True, search=True),
    **_res("options", get=True, create=True, link=True, search=True),
    **_res("parameter_fields", get=True, create=True, link=True, search=True),
    **_res("parameters", get=True, search=True),
    **_res("personas", get=True, create=True, link=True, search=True),
    **_res("points", get=True, create=True, search=True),
    **_res("pricing", get=True, create=True, search=True),
    **_res("problem_statements", get=True, create=True, link=True, search=True),
    **_res("profile_personas", get=True, create=True, link=True, search=True),
    **_res("profiles", get=True, link=True, search=True),
    **_res("prompts", get=True, create=True, search=True),
    **_res("protocols", get=True, create=True, search=True),
    **_res("provider_keys", get=True, create=True, search=True),
    **_res("providers", get=True, search=True),
    **_res("qualities", get=True, search=True),
    **_res("questions", get=True, create=True, link=True, search=True),
    **_res("reasoning_levels", get=True, search=True),
    **_res("request_limits", get=True, create=True, search=True),
    **_res("roles", get=True, search=True),
    **_res("rubrics", get=True, search=True),
    **_res("run_positions", get=True, create=True, search=True),
    **_res("run_rubrics", get=True, create=True, search=True),
    **_res("runs", get=True, search=True),
    **_res("scenario_flags", get=True, link=True, search=True),
    **_res("scenario_positions", get=True, create=True, link=True, search=True),
    **_res("scenario_rubrics", get=True, create=True, link=True, search=True),
    **_res("scenario_time_limits", get=True, create=True, link=True, search=True),
    **_res("scenarios", get=True, create=True, link=True, search=True),
    **_res("settings", get=True, search=True),
    **_res("simulation_availability", get=True, create=True, link=True, search=True),
    **_res("simulation_positions", get=True, create=True, link=True, search=True),
    **_res("simulations", get=True, create=True, link=True, search=True),
    **_res("slugs", get=True, create=True, search=True),
    **_res("standard_groups", get=True, create=True, search=True),
    **_res("standards", get=True, search=True),
    **_res("temperature_levels", get=True, search=True),
    **_res("texts", get=True, create=True, search=True),
    **_res("thresholds", get=True, search=True),
    **_res("tools", get=True, search=True),
    **_res("uploads", get=True, create=True, search=True),
    **_res("values", get=True, create=True, search=True),
    **_res("videos", get=True, create=True, link=True, search=True),
    **_res("voices", get=True, create=True, link=True, search=True),
}

# ---------------------------------------------------------------------------
# Entry operations: (entry_name, op) → (module_path, function_name) | None
#
# Naming conventions (actual):
#   get    → get_{name}_entries_internal
#   search → search_{name}_entries_internal
#   create → create_{name}_entry_internal
#   docs   → None (not yet implemented)
#
# Notable exceptions (non-standard get function names):
#   chat           → get_chat_entries_internal
#   logins         → get_login_list_view_internal
#   problems       → get_problem_list_view_internal
#   attempt_responses → get_simulation_responses_internal
# ---------------------------------------------------------------------------

_E = "app.tools.entries"


def _ent(
    name: str,
    *,
    get: bool = True,
    get_fn: str | None = None,
    search: bool = True,
    create: bool = False,
) -> dict[tuple[str, str], tuple[str, str] | None]:
    """Helper to generate entry op entries."""
    d: dict[tuple[str, str], tuple[str, str] | None] = {}
    if get:
        fn = get_fn or f"get_{name}_entries_internal"
        d[(name, "get")] = (f"{_E}.{name}.get", fn)
    else:
        d[(name, "get")] = None
    d[(name, "search")] = (
        (f"{_E}.{name}.search", f"search_{name}_entries_internal") if search else None
    )
    d[(name, "create")] = (
        (f"{_E}.{name}.create", f"create_{name}_entry_internal") if create else None
    )
    d[(name, "docs")] = None
    return d


ENTRY_OPS: dict[tuple[str, str], tuple[str, str] | None] = {
    **_ent("activity"),
    **_ent("agent_drafts"),
    **_ent("attempt", create=True),
    **_ent("attempt_analysis", create=True),
    **_ent("attempt_archive", create=True),
    **_ent("attempt_chat", create=True),
    **_ent("attempt_completion", create=True),
    **_ent("attempt_content", create=True),
    **_ent("attempt_feedback", create=True),
    **_ent("attempt_grade", create=True),
    **_ent("attempt_highlight", create=True),
    **_ent("attempt_hint", create=True),
    **_ent("attempt_improvement", create=True),
    **_ent("attempt_message", create=True),
    **_ent("attempt_message_tree"),
    **_ent("attempt_replacement", create=True),
    **_ent("attempt_strength", create=True),
    **_ent("audios"),
    **_ent("auth_drafts"),
    **_ent("benchmark"),
    **_ent("calls"),
    **_ent("chat", get_fn="get_chat_entries_internal", search=False),
    **_ent("cohort_drafts"),
    **_ent("config"),
    **_ent("attempt_conversations", create=True),
    **_ent("attempt_conversation_completions", create=True),
    **_ent("department_drafts"),
    **_ent("document_drafts"),
    **_ent("emulations"),
    **_ent("eval_drafts"),
    **_ent("field_drafts"),
    **_ent("grants"),
    **_ent("groups"),
    **_ent("health"),
    **_ent("home"),
    **_ent("images"),
    **_ent("logins", get_fn="get_login_list_view_internal"),
    **_ent("messages"),
    **_ent("messages_completions"),
    **_ent("metrics"),
    **_ent("model_drafts"),
    **_ent("attempt_mutes", create=True),
    **_ent("parameter_drafts"),
    **_ent("persona"),
    **_ent("persona_drafts"),
    **_ent("practice"),
    **_ent("problems", get_fn="get_problem_list_view_internal", create=True),
    **_ent("profile_drafts"),
    **_ent("provider_drafts"),
    **_ent("resolves", create=True),
    **_ent(
        "attempt_responses", get_fn="get_simulation_responses_internal", create=True
    ),
    **_ent("rubric_drafts"),
    **_ent("run_pricing"),
    **_ent("runs"),
    **_ent("scenario_drafts"),
    **_ent("sessions"),
    **_ent("setting_drafts"),
    **_ent("simulation_drafts"),
    **_ent("test", create=True),
    **_ent("test_archive", create=True),
    **_ent("test_completion", create=True),
    **_ent("test_feedback", create=True),
    **_ent("test_grade", create=True),
    **_ent("test_invocation", create=True),
    **_ent("texts"),
    **_ent("tokens"),
    **_ent("tool_drafts"),
    **_ent("uploads"),
    **_ent("uploads_completions"),
    **_ent("videos"),
}

# ---------------------------------------------------------------------------
# Infra operations: (artifact_name, op) → (module_path, function_name) | None
#
# Maps (artifact, operation) to the infra-level API implementation function.
# These are the functions behind HTTP routes and socket events — they handle
# permissions, value resolution, denormalized snapshots, and cache invalidation.
#
# A tool's permission_ids → permissions_resource.(artifact, operation) resolves
# to a key in this dict, giving the actual function to call.
#
# Naming conventions:
#   create    → create_{name}_impl
#   update    → update_{name}_impl
#   delete    → delete_{name}_impl
#   search    → search_{name}_impl
#   get       → get_{name}_impl
#   draft     → patch_{name}_draft_impl
#   drafts    → list_{name}_drafts_impl
#   duplicate → duplicate_{name}_impl
#   export    → export_{name}_impl
#   refresh   → refresh_{name}_impl
#   docs      → docs_{name}_impl
#
# Attempt/test state-machine operations use {name}_{op}_internal_impl.
# ---------------------------------------------------------------------------

_I = "app.infra"


def _infra(
    name: str,
    *,
    # Standard CRUD
    create: bool = False,
    update: bool = False,
    delete: bool = False,
    search: bool = False,
    get: bool = False,
    draft: bool = False,
    drafts: bool = False,
    duplicate: bool = False,
    export: bool = False,
    refresh: bool = False,
    docs: bool = False,
    csv: bool = False,
    # Media operations
    image_upload: bool = False,
    image_download: bool = False,
    video_upload: bool = False,
    video_download: bool = False,
    text_upload: bool = False,
    text_download: bool = False,
    file_upload: bool = False,
    file_download: bool = False,
    file_preview: bool = False,
    audio_start: bool = False,
    audio_frame: bool = False,
    audio_stop: bool = False,
    audio_mute: bool = False,
    audio_upload: bool = False,
    audio_download: bool = False,
    call_download: bool = False,
) -> dict[tuple[str, str], tuple[str, str] | None]:
    """Helper to generate infra op entries for a standard artifact."""
    d: dict[tuple[str, str], tuple[str, str] | None] = {}
    if create:
        d[(name, "create")] = (f"{_I}.{name}.create", f"create_{name}_impl")
    if update:
        d[(name, "update")] = (f"{_I}.{name}.update", f"update_{name}_impl")
    if delete:
        d[(name, "delete")] = (f"{_I}.{name}.delete", f"delete_{name}_impl")
    if search:
        d[(name, "search")] = (f"{_I}.{name}.search", f"search_{name}_impl")
    if get:
        d[(name, "get")] = (f"{_I}.{name}.get", f"get_{name}_impl")
    if draft:
        d[(name, "draft")] = (f"{_I}.{name}.draft", f"patch_{name}_draft_impl")
    if drafts:
        d[(name, "drafts")] = (f"{_I}.{name}.drafts", f"list_{name}_drafts_impl")
    if duplicate:
        d[(name, "duplicate")] = (f"{_I}.{name}.duplicate", f"duplicate_{name}_impl")
    if export:
        d[(name, "export")] = (f"{_I}.{name}.export", f"export_{name}_impl")
    if refresh:
        d[(name, "refresh")] = (f"{_I}.{name}.refresh", f"refresh_{name}_impl")
    if docs:
        d[(name, "docs")] = (f"{_I}.{name}.docs", f"docs_{name}_impl")
    if csv:
        d[(name, "csv")] = (f"{_I}.{name}.csv", f"csv_{name}_impl")
    # Media operations
    if image_upload:
        d[(name, "image_upload")] = (f"{_I}.{name}.image_upload", f"image_upload_{name}_impl")
    if image_download:
        d[(name, "image_download")] = (f"{_I}.{name}.image_download", f"image_download_{name}_impl")
    if video_upload:
        d[(name, "video_upload")] = (f"{_I}.{name}.video_upload", f"video_upload_{name}_impl")
    if video_download:
        d[(name, "video_download")] = (f"{_I}.{name}.video_download", f"video_download_{name}_impl")
    if text_upload:
        d[(name, "text_upload")] = (f"{_I}.{name}.text_upload", f"text_upload_{name}_impl")
    if text_download:
        d[(name, "text_download")] = (f"{_I}.{name}.text_download", f"text_download_{name}_impl")
    if file_upload:
        d[(name, "file_upload")] = (f"{_I}.{name}.file_upload", f"file_upload_{name}_impl")
    if file_download:
        d[(name, "file_download")] = (f"{_I}.{name}.file_download", f"file_download_{name}_impl")
    if file_preview:
        d[(name, "file_preview")] = (f"{_I}.{name}.file_preview", f"file_preview_{name}_impl")
    if audio_start:
        d[(name, "audio_start")] = (f"{_I}.{name}.audio_start", f"audio_start_{name}_impl")
    if audio_frame:
        d[(name, "audio_frame")] = (f"{_I}.{name}.audio_frame", f"audio_frame_{name}_impl")
    if audio_stop:
        d[(name, "audio_stop")] = (f"{_I}.{name}.audio_stop", f"audio_stop_{name}_impl")
    if audio_mute:
        d[(name, "audio_mute")] = (f"{_I}.{name}.audio_mute", f"audio_mute_{name}_impl")
    if audio_upload:
        d[(name, "audio_upload")] = (f"{_I}.{name}.audio_upload", f"audio_upload_{name}_impl")
    if audio_download:
        d[(name, "audio_download")] = (f"{_I}.{name}.audio_download", f"audio_download_{name}_impl")
    if call_download:
        d[(name, "call_download")] = (f"{_I}.{name}.call_download", f"call_download_{name}_impl")
    return d


# Standard CRUD artifacts (create, update, delete, search, get, draft, drafts,
# duplicate, export, refresh, docs)
_FULL_CRUD = dict(
    create=True, update=True, delete=True, search=True, get=True,
    draft=True, drafts=True, duplicate=True, export=True, refresh=True, docs=True,
)

INFRA_OPS: dict[tuple[str, str], tuple[str, str] | None] = {
    # --- Full CRUD artifacts ---
    **_infra("agent", **_FULL_CRUD, csv=True),
    **_infra("auth", **_FULL_CRUD),
    **_infra("cohort", **_FULL_CRUD, csv=True),
    **_infra("department", **_FULL_CRUD, csv=True),
    **_infra("document", **_FULL_CRUD, csv=True,
             text_upload=True, text_download=True,
             file_upload=True, file_download=True, file_preview=True),
    **_infra("eval", **_FULL_CRUD, csv=True),
    **_infra("field", **_FULL_CRUD, csv=True),
    **_infra("model", **_FULL_CRUD, csv=True),
    **_infra("parameter", **_FULL_CRUD, csv=True),
    **_infra("persona", **_FULL_CRUD, csv=True),
    **_infra("profile", **_FULL_CRUD),
    **_infra("provider", **_FULL_CRUD, csv=True),
    **_infra("rubric", **_FULL_CRUD, csv=True),
    **_infra("scenario", **_FULL_CRUD, csv=True,
             image_upload=True, image_download=True,
             video_upload=True, video_download=True,
             text_download=True,
             file_download=True, file_preview=True),
    **_infra("setting", **_FULL_CRUD, csv=True),
    **_infra("simulation", **_FULL_CRUD, csv=True),
    **_infra("tool", **_FULL_CRUD),
    # --- View + partial artifacts ---
    **_infra("activity", export=True, refresh=True, docs=True),
    **_infra("benchmark", get=True, export=True, refresh=True, docs=True),
    **_infra("chat", get=True, draft=True, drafts=True, export=True, refresh=True, docs=True),
    **_infra("dashboard", export=True, refresh=True, docs=True),
    **_infra("group", get=True, export=True, refresh=True, docs=True,
             image_download=True, video_download=True,
             text_download=True,
             file_download=True, file_preview=True,
             audio_download=True, call_download=True),
    ("group", "name"): ("app.infra.group.name", "name_group_impl"),
    **_infra("health", get=True, export=True, refresh=True, docs=True),
    **_infra("invocation", get=True, draft=True, drafts=True, export=True, refresh=True, docs=True),
    **_infra("leaderboard", export=True, refresh=True, docs=True),
    **_infra("pricing", get=True, export=True, refresh=True, docs=True),
    **_infra("reports", get=True, export=True, refresh=True, docs=True),
    **_infra("session", get=True, export=True, refresh=True, docs=True),
    **_infra("test", get=True, search=True, export=True, refresh=True, docs=True,
             text_download=True, call_download=True),
    # --- Attempt state-machine + media operations ---
    ("attempt", "get"): (f"{_I}.attempt.get", "get_attempt_impl"),
    ("attempt", "search"): (f"{_I}.attempt.search", "search_attempt_impl"),
    ("attempt", "export"): (f"{_I}.attempt.export", "export_attempt_impl"),
    ("attempt", "refresh"): (f"{_I}.attempt.refresh", "refresh_attempt_impl"),
    ("attempt", "docs"): (f"{_I}.attempt.docs", "docs_attempt_impl"),
    ("attempt", "start"): (f"{_I}.attempt.start", "attempt_start_internal_impl"),
    ("attempt", "end"): (f"{_I}.attempt.end", "attempt_end_internal_impl"),
    ("attempt", "end_all"): (f"{_I}.attempt.end_all", "attempt_end_all_internal_impl"),
    ("attempt", "next"): (f"{_I}.attempt.next", "attempt_next_internal_impl"),
    ("attempt", "message"): (f"{_I}.attempt.message", "attempt_message_internal_impl"),
    ("attempt", "grade"): (f"{_I}.attempt.grade", "attempt_grade_internal_impl"),
    ("attempt", "stop"): (f"{_I}.attempt.stop", "attempt_stop_internal_impl"),
    ("attempt", "response"): (f"{_I}.attempt.response", "attempt_response_internal_impl"),
    ("attempt", "previous"): (f"{_I}.attempt.previous", "attempt_previous_internal_impl"),
    ("attempt", "audio_start"): (f"{_I}.attempt.audio_start", "audio_start_attempt_impl"),
    ("attempt", "audio_frame"): (f"{_I}.attempt.audio_frame", "audio_frame_attempt_impl"),
    ("attempt", "audio_stop"): (f"{_I}.attempt.audio_stop", "audio_stop_attempt_impl"),
    ("attempt", "audio_mute"): (f"{_I}.attempt.audio_mute", "audio_mute_attempt_impl"),
    ("attempt", "audio_upload"): (f"{_I}.attempt.audio_upload", "audio_upload_attempt_impl"),
    ("attempt", "audio_download"): (f"{_I}.attempt.audio_download", "audio_download_attempt_impl"),
    ("attempt", "image_download"): (f"{_I}.attempt.image_download", "image_download_attempt_impl"),
    ("attempt", "video_download"): (f"{_I}.attempt.video_download", "video_download_attempt_impl"),
    ("attempt", "text_download"): (f"{_I}.attempt.text_download", "text_download_attempt_impl"),
    ("attempt", "file_download"): (f"{_I}.attempt.file_download", "file_download_attempt_impl"),
    ("attempt", "file_preview"): (f"{_I}.attempt.file_preview", "file_preview_attempt_impl"),
    # --- Test state-machine operations ---
    ("test", "start"): (f"{_I}.test.start", "test_start_internal_impl"),
    ("test", "end"): (f"{_I}.test.end", "test_end_internal_impl"),
    ("test", "next"): (f"{_I}.test.next", "test_next_internal_impl"),
    ("test", "grade"): ("app.infra.test.grade", "create_grade_impl"),
    ("test", "feedback"): ("app.infra.test.feedback", "create_feedback_impl"),
}

# ---------------------------------------------------------------------------
# Infra item types: (artifact_name, op) → (module_path, class_name)
#
# Maps (artifact, operation) to the Pydantic item class that defines
# what input fields the operation accepts. This is the source of truth
# for what a tool's args_outputs can produce for a given target operation.
#
# At runtime: import the class, inspect its fields, construct from
# rendered template values, and pass to the infra function.
#
# Naming conventions:
#   create → Create{Name}Item   in app.infra.{name}.types
#   update → Update{Name}Item   in app.infra.{name}.types
# ---------------------------------------------------------------------------

_IT = "app.infra"


def _item_types(
    name: str,
    class_name: str,
    *,
    create: bool = True,
    update: bool = True,
) -> dict[tuple[str, str], tuple[str, str]]:
    """Helper to generate item type entries for a standard artifact."""
    d: dict[tuple[str, str], tuple[str, str]] = {}
    if create:
        d[(name, "create")] = (f"{_IT}.{name}.types", f"Create{class_name}Item")
    if update:
        d[(name, "update")] = (f"{_IT}.{name}.types", f"Update{class_name}Item")
    return d


INFRA_ITEM_TYPES: dict[tuple[str, str], tuple[str, str]] = {
    **_item_types("agent", "Agent"),
    **_item_types("auth", "Auth"),
    **_item_types("cohort", "Cohort"),
    **_item_types("department", "Department"),
    **_item_types("document", "Document"),
    **_item_types("eval", "Eval"),
    **_item_types("field", "Field"),
    **_item_types("model", "Model"),
    **_item_types("parameter", "Parameter"),
    **_item_types("persona", "Persona"),
    **_item_types("profile", "Profile"),
    **_item_types("provider", "Provider"),
    **_item_types("rubric", "Rubric"),
    **_item_types("scenario", "Scenario"),
    **_item_types("setting", "Setting"),
    **_item_types("simulation", "Simulation"),
    **_item_types("tool", "Tool"),
}


def resolve_item_class(
    artifact: str,
    operation: str,
) -> type | None:
    """Look up (artifact, operation) and return the imported Pydantic item class.

    Returns None if no item type is registered for this pair.
    """
    entry = INFRA_ITEM_TYPES.get((artifact, operation))
    if entry is None:
        return None
    module_path, class_name = entry
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def resolve_request_class(
    artifact: str,
    operation: str,
) -> type | None:
    """Derive the API request wrapper class from the item type entry.

    Convention: CreateFooItem → CreateFooApiRequest (same module).
    Returns None if no item type is registered.
    """
    entry = INFRA_ITEM_TYPES.get((artifact, operation))
    if entry is None:
        return None
    module_path, class_name = entry
    # CreateFooItem → CreateFooApiRequest, UpdateFooItem → UpdateFooApiRequest
    # PatchFooDraftApiRequest → already IS the request class (no wrapper)
    if class_name.endswith("ApiRequest"):
        # Draft-style: the item IS the request (flat, no wrapper)
        return None
    request_class_name = class_name.replace("Item", "ApiRequest")
    mod = importlib.import_module(module_path)
    return getattr(mod, request_class_name, None)


def get_accepted_fields(artifact: str, operation: str) -> set[str] | None:
    """Return the set of field names the item class accepts.

    Useful for validating that a tool's args_outputs only produce
    fields that the target operation understands.
    """
    cls = resolve_item_class(artifact, operation)
    if cls is None:
        return None
    return set(cls.model_fields.keys())
