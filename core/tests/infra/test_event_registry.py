"""Tests for the centralized event registry contract."""

from app.infra.stream.registry import get_artifact_events_config


def test_registry_resolves_persona_config() -> None:
    config = get_artifact_events_config("persona")

    assert config is not None
    assert config.artifact == "persona"
    assert "get" in config.operations
    assert "artifacts.persona.viewed" in config.event_types


def test_registry_resolves_activity_config() -> None:
    config = get_artifact_events_config("activity")

    assert config is not None
    assert config.artifact == "activity"
    assert "get" in config.operations
    assert "artifacts.activity.viewed" in config.event_types


def test_registry_resolves_attempt_config() -> None:
    config = get_artifact_events_config("attempt")

    assert config is not None
    assert config.artifact == "attempt"
    assert "message" in config.operations
    assert "artifacts.attempt.assistant.progress" in config.event_types


def test_registry_resolves_auth_config() -> None:
    config = get_artifact_events_config("auth")

    assert config is not None
    assert config.artifact == "auth"
    assert "get" in config.operations
    assert "artifacts.auth.viewed" in config.event_types


def test_registry_resolves_benchmark_config() -> None:
    config = get_artifact_events_config("benchmark")

    assert config is not None
    assert config.artifact == "benchmark"
    assert "get" in config.operations
    assert "artifacts.benchmark.viewed" in config.event_types


def test_registry_resolves_chat_config() -> None:
    config = get_artifact_events_config("chat")

    assert config is not None
    assert config.artifact == "chat"
    assert "get" in config.operations
    assert "artifacts.chat.viewed" in config.event_types


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


def test_registry_resolves_dashboard_config() -> None:
    config = get_artifact_events_config("dashboard")

    assert config is not None
    assert config.artifact == "dashboard"
    assert "get" in config.operations
    assert "artifacts.dashboard.viewed" in config.event_types


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


def test_registry_resolves_health_config() -> None:
    config = get_artifact_events_config("health")

    assert config is not None
    assert config.artifact == "health"
    assert "get" in config.operations
    assert "artifacts.health.viewed" in config.event_types


def test_registry_resolves_home_config() -> None:
    config = get_artifact_events_config("home")

    assert config is not None
    assert config.artifact == "home"
    assert "get" in config.operations
    assert "artifacts.home.viewed" in config.event_types


def test_registry_resolves_invocation_config() -> None:
    config = get_artifact_events_config("invocation")

    assert config is not None
    assert config.artifact == "invocation"
    assert "get" in config.operations
    assert "artifacts.invocation.viewed" in config.event_types


def test_registry_resolves_leaderboard_config() -> None:
    config = get_artifact_events_config("leaderboard")

    assert config is not None
    assert config.artifact == "leaderboard"
    assert "get" in config.operations
    assert "artifacts.leaderboard.viewed" in config.event_types


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


def test_registry_resolves_practice_config() -> None:
    config = get_artifact_events_config("practice")

    assert config is not None
    assert config.artifact == "practice"
    assert "get" in config.operations
    assert "artifacts.practice.viewed" in config.event_types


def test_registry_resolves_rubric_config() -> None:
    config = get_artifact_events_config("rubric")

    assert config is not None
    assert config.artifact == "rubric"
    assert "get" in config.operations
    assert "artifacts.rubric.viewed" in config.event_types


def test_registry_returns_none_for_unknown_artifact() -> None:
    assert get_artifact_events_config("unknown") is None


def test_registry_resolves_session_config() -> None:
    config = get_artifact_events_config("session")

    assert config is not None
    assert config.artifact == "session"
    assert "get" in config.operations
    assert "artifacts.session.viewed" in config.event_types


def test_registry_resolves_record_config() -> None:
    config = get_artifact_events_config("record")

    assert config is not None
    assert config.artifact == "record"
    assert "get" in config.operations
    assert "artifacts.record.viewed" in config.event_types


def test_registry_resolves_reports_config() -> None:
    config = get_artifact_events_config("reports")

    assert config is not None
    assert config.artifact == "reports"
    assert "refresh" in config.operations
    assert "artifacts.reports.refreshed" in config.event_types


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
