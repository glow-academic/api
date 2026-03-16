"""Flat operation registry: (name, op) → (module, func) or None.

Each layer (artifacts, resources, entries) has a dict mapping
``(name, operation)`` to either a ``(module_path, function_name)`` tuple
or ``None`` when the operation is not yet implemented.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any


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

_A = "app.routes.v5"

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
