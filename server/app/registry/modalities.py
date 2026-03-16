"""Output modality registry — (operation, target_name) → required output modalities.

Describes what output modalities a model must support to execute a tool.
Keys are composite: (operation, name) derived from tools_resource columns.

- "call" = model produces structured function/tool calls (default for everything)
- "audio" / "video" / "image" = model produces that media directly
- "text" is never an output modality — all structured output goes through "call"
"""

from __future__ import annotations

_CALL: frozenset[str] = frozenset({"call"})

# ---------------------------------------------------------------------------
# Resources — (operation, resource_name) → required output modalities
# Resources are references/metadata; always "call".
# ---------------------------------------------------------------------------
RESOURCE_MODALITIES: dict[tuple[str, str], frozenset[str]] = {
    # create
    ("create", "agents"): _CALL,
    ("create", "arg_positions"): _CALL,
    ("create", "args"): _CALL,
    ("create", "args_outputs"): _CALL,
    ("create", "auths"): _CALL,
    ("create", "cohorts"): _CALL,
    ("create", "colors"): _CALL,
    ("create", "departments"): _CALL,
    ("create", "descriptions"): _CALL,
    ("create", "documents"): _CALL,
    ("create", "emails"): _CALL,
    ("create", "endpoints"): _CALL,
    ("create", "examples"): _CALL,
    ("create", "fields"): _CALL,
    ("create", "flags"): _CALL,
    ("create", "group_positions"): _CALL,
    ("create", "group_rubrics"): _CALL,
    ("create", "groups"): _CALL,
    ("create", "icons"): _CALL,
    ("create", "images"): _CALL,
    ("create", "instructions"): _CALL,
    ("create", "items"): _CALL,
    ("create", "keys"): _CALL,
    ("create", "modalities"): _CALL,
    ("create", "models"): _CALL,
    ("create", "names"): _CALL,
    ("create", "objectives"): _CALL,
    ("create", "options"): _CALL,
    ("create", "parameter_fields"): _CALL,
    ("create", "parameters"): _CALL,
    ("create", "personas"): _CALL,
    ("create", "points"): _CALL,
    ("create", "pricing"): _CALL,
    ("create", "problem_statements"): _CALL,
    ("create", "profile_personas"): _CALL,
    ("create", "profiles"): _CALL,
    ("create", "prompts"): _CALL,
    ("create", "protocols"): _CALL,
    ("create", "providers"): _CALL,
    ("create", "qualities"): _CALL,
    ("create", "questions"): _CALL,
    ("create", "reasoning_levels"): _CALL,
    ("create", "request_limits"): _CALL,
    ("create", "run_positions"): _CALL,
    ("create", "run_rubrics"): _CALL,
    ("create", "runs"): _CALL,
    ("create", "scenario_flags"): _CALL,
    ("create", "scenario_personas"): _CALL,
    ("create", "scenario_positions"): _CALL,
    ("create", "scenario_rubrics"): _CALL,
    ("create", "scenario_time_limits"): _CALL,
    ("create", "scenarios"): _CALL,
    ("create", "settings"): _CALL,
    ("create", "simulation_availability"): _CALL,
    ("create", "simulation_positions"): _CALL,
    ("create", "simulations"): _CALL,
    ("create", "slugs"): _CALL,
    ("create", "standard_groups"): _CALL,
    ("create", "standards"): _CALL,
    ("create", "temperature_levels"): _CALL,
    ("create", "thresholds"): _CALL,
    ("create", "uploads"): _CALL,
    ("create", "values"): _CALL,
    ("create", "videos"): _CALL,
    ("create", "voices"): _CALL,
    # link
    ("link", "agents"): _CALL,
    ("link", "auths"): _CALL,
    ("link", "cohorts"): _CALL,
    ("link", "colors"): _CALL,
    ("link", "departments"): _CALL,
    ("link", "descriptions"): _CALL,
    ("link", "documents"): _CALL,
    ("link", "evals"): _CALL,
    ("link", "examples"): _CALL,
    ("link", "fields"): _CALL,
    ("link", "flags"): _CALL,
    ("link", "groups"): _CALL,
    ("link", "icons"): _CALL,
    ("link", "images"): _CALL,
    ("link", "instructions"): _CALL,
    ("link", "modalities"): _CALL,
    ("link", "models"): _CALL,
    ("link", "names"): _CALL,
    ("link", "objectives"): _CALL,
    ("link", "options"): _CALL,
    ("link", "parameter_fields"): _CALL,
    ("link", "parameters"): _CALL,
    ("link", "personas"): _CALL,
    ("link", "problem_statements"): _CALL,
    ("link", "profile_personas"): _CALL,
    ("link", "profiles"): _CALL,
    ("link", "providers"): _CALL,
    ("link", "qualities"): _CALL,
    ("link", "questions"): _CALL,
    ("link", "reasoning_levels"): _CALL,
    ("link", "rubrics"): _CALL,
    ("link", "runs"): _CALL,
    ("link", "scenario_flags"): _CALL,
    ("link", "scenario_personas"): _CALL,
    ("link", "scenario_positions"): _CALL,
    ("link", "scenario_rubrics"): _CALL,
    ("link", "scenario_time_limits"): _CALL,
    ("link", "scenarios"): _CALL,
    ("link", "settings"): _CALL,
    ("link", "simulation_availability"): _CALL,
    ("link", "simulation_positions"): _CALL,
    ("link", "simulations"): _CALL,
    ("link", "temperature_levels"): _CALL,
    ("link", "thresholds"): _CALL,
    ("link", "videos"): _CALL,
    ("link", "voices"): _CALL,
}

# ---------------------------------------------------------------------------
# Entries — (operation, entry_name) → required output modalities
# Most entries are "call". Media entries require their media modality.
# ---------------------------------------------------------------------------
ENTRY_MODALITIES: dict[tuple[str, str], frozenset[str]] = {
    ("create", "activities"): _CALL,
    ("create", "analyses"): _CALL,
    ("create", "attempt_archives"): _CALL,
    ("create", "attempt_chats"): _CALL,
    ("create", "attempt_completions"): _CALL,
    ("create", "attempt_grades"): _CALL,
    ("create", "attempt_insights"): _CALL,
    ("create", "attempt_messages"): _CALL,
    ("create", "attempts"): _CALL,
    ("create", "audios"): frozenset({"audio"}),
    ("create", "benchmark_insights"): _CALL,
    ("create", "calls"): _CALL,
    ("create", "contents"): _CALL,
    ("create", "attempt_conversations"): _CALL,
    ("create", "attempt_conversation_completions"): _CALL,
    ("create", "emulations"): _CALL,
    ("create", "feedbacks"): _CALL,
    ("create", "files"): _CALL,
    ("create", "grants"): _CALL,
    ("create", "highlights"): _CALL,
    ("create", "hints"): _CALL,
    ("create", "images"): frozenset({"image"}),
    ("create", "improvements"): _CALL,
    ("create", "logins"): _CALL,
    ("create", "messages"): _CALL,
    ("create", "messages_completions"): _CALL,
    ("create", "metrics"): _CALL,
    ("create", "attempt_mutes"): _CALL,
    ("create", "problems"): _CALL,
    ("create", "replacements"): _CALL,
    ("create", "resolves"): _CALL,
    ("create", "run_pricing"): _CALL,
    ("create", "sessions"): _CALL,
    ("create", "strengths"): _CALL,
    ("create", "test_archives"): _CALL,
    ("create", "test_completions"): _CALL,
    ("create", "test_feedbacks"): _CALL,
    ("create", "test_grades"): _CALL,
    ("create", "test_insights"): _CALL,
    ("create", "test_invocations"): _CALL,
    ("create", "tests"): _CALL,
    ("create", "tokens"): _CALL,
    ("create", "uploads_completions"): _CALL,
    ("create", "videos"): frozenset({"video"}),
}

# ---------------------------------------------------------------------------
# Artifacts — (operation, artifact_name) → required output modalities
# Artifacts are always "call".
# ---------------------------------------------------------------------------
ARTIFACT_MODALITIES: dict[tuple[str, str], frozenset[str]] = {
    ("delete", "cohort"): _CALL,
    ("delete", "persona"): _CALL,
    ("delete", "scenario"): _CALL,
    ("delete", "simulation"): _CALL,
    ("docs", "activity"): _CALL,
    ("docs", "attempt"): _CALL,
    ("docs", "cohort"): _CALL,
    ("docs", "dashboard"): _CALL,
    ("docs", "group"): _CALL,
    ("docs", "health"): _CALL,
    ("docs", "leaderboard"): _CALL,
    ("docs", "persona"): _CALL,
    ("docs", "pricing"): _CALL,
    ("docs", "reports"): _CALL,
    ("docs", "scenario"): _CALL,
    ("docs", "session"): _CALL,
    ("docs", "simulation"): _CALL,
    ("docs", "test"): _CALL,
    ("duplicate", "cohort"): _CALL,
    ("duplicate", "persona"): _CALL,
    ("duplicate", "scenario"): _CALL,
    ("duplicate", "simulation"): _CALL,
    ("get", "activity"): _CALL,
    ("get", "attempt"): _CALL,
    ("get", "cohort"): _CALL,
    ("get", "dashboard"): _CALL,
    ("get", "group"): _CALL,
    ("get", "health"): _CALL,
    ("get", "home"): _CALL,
    ("get", "leaderboard"): _CALL,
    ("get", "persona"): _CALL,
    ("get", "practice"): _CALL,
    ("get", "pricing"): _CALL,
    ("get", "record"): _CALL,
    ("get", "reports"): _CALL,
    ("get", "scenario"): _CALL,
    ("get", "session"): _CALL,
    ("get", "simulation"): _CALL,
    ("get", "test"): _CALL,
    ("list", "cohort"): _CALL,
    ("list", "persona"): _CALL,
    ("list", "scenario"): _CALL,
    ("list", "simulation"): _CALL,
    ("save", "cohort"): _CALL,
    ("save", "persona"): _CALL,
    ("save", "scenario"): _CALL,
    ("save", "simulation"): _CALL,
}

# ---------------------------------------------------------------------------
# Default fallback
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_MODALITIES: frozenset[str] = _CALL


def get_tool_output_modalities(
    operation: str | None,
    resources: list[str] | None,
    entries: list[str] | None,
    artifacts: list[str] | None,
) -> frozenset[str]:
    """Derive required output modalities from a tool's columns.

    Returns the union of required modalities across all targets.
    Falls back to {"call"} if nothing matches.
    """
    if not operation:
        return DEFAULT_OUTPUT_MODALITIES

    modalities: set[str] = set()

    for name in resources or []:
        modalities |= RESOURCE_MODALITIES.get(
            (operation, name), DEFAULT_OUTPUT_MODALITIES
        )
    for name in entries or []:
        modalities |= ENTRY_MODALITIES.get((operation, name), DEFAULT_OUTPUT_MODALITIES)
    for name in artifacts or []:
        modalities |= ARTIFACT_MODALITIES.get(
            (operation, name), DEFAULT_OUTPUT_MODALITIES
        )

    return frozenset(modalities) if modalities else DEFAULT_OUTPUT_MODALITIES
