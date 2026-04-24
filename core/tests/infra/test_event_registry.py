"""Tests for the centralized event registry contract.

Post 19→3 consolidation, the former satellite artifacts (chat, record,
practice, home, reports, dashboard, leaderboard, benchmark, invocation,
activity, group, health, session) are no longer top-level registry keys —
their operations are merged into their parent artifacts
(attempt / test / system) under the canonical underscored operation names.
"""

from app.infra.stream.registry import EVENT_REGISTRY, get_artifact_events_config


def test_registry_resolves_persona_config() -> None:
    config = get_artifact_events_config("persona")

    assert config is not None
    assert config.artifact == "persona"
    assert "get" in config.operations
    assert "artifacts.persona.viewed" in config.event_types


def test_registry_resolves_attempt_config() -> None:
    config = get_artifact_events_config("attempt")

    assert config is not None
    assert config.artifact == "attempt"
    assert "message" in config.operations
    assert "artifacts.attempt.chat.assistant.progress" in config.event_types


def test_registry_resolves_auth_config() -> None:
    config = get_artifact_events_config("auth")

    assert config is not None
    assert config.artifact == "auth"
    assert "get" in config.operations
    assert "artifacts.auth.viewed" in config.event_types


def test_registry_resolves_scenario_config() -> None:
    config = get_artifact_events_config("scenario")

    assert config is not None
    assert config.artifact == "scenario"
    assert "get" in config.operations
    assert "artifacts.scenario.viewed" in config.event_types


def test_registry_resolves_agent_config() -> None:
    config = get_artifact_events_config("agent")

    assert config is not None
    assert config.artifact == "agent"
    assert "get" in config.operations
    assert "artifacts.agent.viewed" in config.event_types


def test_registry_resolves_cohort_config() -> None:
    config = get_artifact_events_config("cohort")

    assert config is not None
    assert config.artifact == "cohort"
    assert "get" in config.operations
    assert "artifacts.cohort.viewed" in config.event_types


def test_registry_resolves_department_config() -> None:
    config = get_artifact_events_config("department")

    assert config is not None
    assert config.artifact == "department"
    assert "get" in config.operations
    assert "artifacts.department.viewed" in config.event_types


def test_registry_resolves_document_config() -> None:
    config = get_artifact_events_config("document")

    assert config is not None
    assert config.artifact == "document"
    assert "get" in config.operations
    assert "artifacts.document.viewed" in config.event_types


def test_registry_resolves_eval_config() -> None:
    config = get_artifact_events_config("eval")

    assert config is not None
    assert config.artifact == "eval"
    assert "get" in config.operations
    assert "artifacts.eval.viewed" in config.event_types


def test_registry_resolves_field_config() -> None:
    config = get_artifact_events_config("field")

    assert config is not None
    assert config.artifact == "field"
    assert "get" in config.operations
    assert "artifacts.field.viewed" in config.event_types


def test_registry_resolves_model_config() -> None:
    config = get_artifact_events_config("model")

    assert config is not None
    assert config.artifact == "model"
    assert "get" in config.operations
    assert "artifacts.model.viewed" in config.event_types


def test_registry_resolves_parameter_config() -> None:
    config = get_artifact_events_config("parameter")

    assert config is not None
    assert config.artifact == "parameter"
    assert "get" in config.operations
    assert "artifacts.parameter.viewed" in config.event_types


def test_registry_resolves_profile_config() -> None:
    config = get_artifact_events_config("profile")

    assert config is not None
    assert config.artifact == "profile"
    assert "get" in config.operations
    assert "artifacts.profile.viewed" in config.event_types


def test_registry_resolves_provider_config() -> None:
    config = get_artifact_events_config("provider")

    assert config is not None
    assert config.artifact == "provider"
    assert "get" in config.operations
    assert "artifacts.provider.viewed" in config.event_types


def test_registry_resolves_pricing_config() -> None:
    config = get_artifact_events_config("pricing")

    assert config is not None
    assert config.artifact == "pricing"
    assert "get" in config.operations
    assert "artifacts.pricing.viewed" in config.event_types


def test_registry_resolves_rubric_config() -> None:
    config = get_artifact_events_config("rubric")

    assert config is not None
    assert config.artifact == "rubric"
    assert "get" in config.operations
    assert "artifacts.rubric.viewed" in config.event_types


def test_registry_returns_none_for_unknown_artifact() -> None:
    assert get_artifact_events_config("unknown") is None


def test_registry_resolves_setting_config() -> None:
    config = get_artifact_events_config("setting")

    assert config is not None
    assert config.artifact == "setting"
    assert "get" in config.operations
    assert "artifacts.setting.viewed" in config.event_types


def test_registry_resolves_simulation_config() -> None:
    config = get_artifact_events_config("simulation")

    assert config is not None
    assert config.artifact == "simulation"
    assert "get" in config.operations
    assert "artifacts.simulation.viewed" in config.event_types


def test_registry_resolves_tool_config() -> None:
    config = get_artifact_events_config("tool")

    assert config is not None
    assert config.artifact == "tool"
    assert "get" in config.operations
    assert "artifacts.tool.viewed" in config.event_types


# ---------------------------------------------------------------------------
# Post-consolidation: satellite artifacts are merged into their parents.
# ---------------------------------------------------------------------------


def test_registry_excludes_satellite_artifacts() -> None:
    """Satellite artifacts must not appear as top-level registry keys."""
    for satellite in (
        "chat",
        "record",
        "practice",
        "home",
        "reports",
        "dashboard",
        "leaderboard",
        "benchmark",
        "invocation",
        "activity",
        "group",
        "health",
        "session",
    ):
        assert satellite not in EVENT_REGISTRY, (
            f"'{satellite}' must be nested under its parent artifact, "
            "not a top-level registry key"
        )
        assert get_artifact_events_config(satellite) is None


def test_attempt_absorbs_chat_record_practice_home_reports_dashboard_leaderboard() -> None:
    config = get_artifact_events_config("attempt")
    assert config is not None
    ops = set(config.operations.keys())
    # Chat operations
    assert {"chat_get", "chat_refresh"}.issubset(ops)
    # Record operations
    assert {"record_get", "record_refresh"}.issubset(ops)
    # Practice operations
    assert {"practice_get", "practice_refresh"}.issubset(ops)
    # Home operations
    assert {"home_get", "home_refresh"}.issubset(ops)
    # Reports operations
    assert {"reports_refresh"}.issubset(ops)
    # Dashboard operations
    assert {"dashboard_get", "dashboard_refresh"}.issubset(ops)
    # Leaderboard operations
    assert {"leaderboard_get", "leaderboard_refresh"}.issubset(ops)
    # Canonical lifecycle event names emerge from the parent artifact
    assert "artifacts.attempt.chat_get.started" in config.event_types
    assert "artifacts.attempt.home_refresh.completed" in config.event_types


def test_test_absorbs_benchmark_invocation() -> None:
    config = get_artifact_events_config("test")
    assert config is not None
    ops = set(config.operations.keys())
    assert {"benchmark_get", "benchmark_refresh"}.issubset(ops)
    assert {"invocation_get", "invocation_refresh"}.issubset(ops)
    assert "artifacts.test.benchmark_viewed" in config.event_types
    assert "artifacts.test.invocation_viewed" in config.event_types


def test_system_absorbs_activity_group_health_session() -> None:
    config = get_artifact_events_config("system")
    assert config is not None
    assert config.artifact == "system"
    ops = set(config.operations.keys())
    assert {"activity_get", "activity_refresh"}.issubset(ops)
    assert {"group_get", "group_generate", "group_refresh"}.issubset(ops)
    assert {"health_get", "health_refresh"}.issubset(ops)
    assert {"session_get", "session_refresh"}.issubset(ops)
    assert "artifacts.system.activity_viewed" in config.event_types
    assert "artifacts.system.group_generate.progress" in config.event_types
