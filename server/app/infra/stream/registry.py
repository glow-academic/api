"""Central registry for artifact event declarations."""

from __future__ import annotations

from app.events.types import ArtifactEventsConfig
from app.events.activity import ACTIVITY_EVENTS
from app.events.agent import AGENT_EVENTS
from app.events.attempt import ATTEMPT_EVENTS
from app.events.auth import AUTH_EVENTS
from app.events.benchmark import BENCHMARK_EVENTS
from app.events.chat import CHAT_EVENTS
from app.events.cohort import COHORT_EVENTS
from app.events.dashboard import DASHBOARD_EVENTS
from app.events.department import DEPARTMENT_EVENTS
from app.events.document import DOCUMENT_EVENTS
from app.events.eval import EVAL_EVENTS
from app.events.field import FIELD_EVENTS
from app.events.group import GROUP_EVENTS
from app.events.health import HEALTH_EVENTS
from app.events.home import HOME_EVENTS
from app.events.invocation import INVOCATION_EVENTS
from app.events.leaderboard import LEADERBOARD_EVENTS
from app.events.model import MODEL_EVENTS
from app.events.parameter import PARAMETER_EVENTS
from app.events.persona import PERSONA_EVENTS
from app.events.practice import PRACTICE_EVENTS
from app.events.pricing import PRICING_EVENTS
from app.events.profile import PROFILE_EVENTS
from app.events.provider import PROVIDER_EVENTS
from app.events.record import RECORD_EVENTS
from app.events.reports import REPORTS_EVENTS
from app.events.rubric import RUBRIC_EVENTS
from app.events.scenario import SCENARIO_EVENTS
from app.events.session import SESSION_EVENTS
from app.events.setting import SETTING_EVENTS
from app.events.simulation import SIMULATION_EVENTS
from app.events.test import TEST_EVENTS
from app.events.tool import TOOL_EVENTS

EVENT_REGISTRY: dict[str, ArtifactEventsConfig] = {
    "activity": ACTIVITY_EVENTS,
    "agent": AGENT_EVENTS,
    "attempt": ATTEMPT_EVENTS,
    "auth": AUTH_EVENTS,
    "benchmark": BENCHMARK_EVENTS,
    "chat": CHAT_EVENTS,
    "cohort": COHORT_EVENTS,
    "dashboard": DASHBOARD_EVENTS,
    "department": DEPARTMENT_EVENTS,
    "document": DOCUMENT_EVENTS,
    "eval": EVAL_EVENTS,
    "field": FIELD_EVENTS,
    "group": GROUP_EVENTS,
    "health": HEALTH_EVENTS,
    "home": HOME_EVENTS,
    "invocation": INVOCATION_EVENTS,
    "leaderboard": LEADERBOARD_EVENTS,
    "model": MODEL_EVENTS,
    "parameter": PARAMETER_EVENTS,
    "persona": PERSONA_EVENTS,
    "pricing": PRICING_EVENTS,
    "practice": PRACTICE_EVENTS,
    "profile": PROFILE_EVENTS,
    "provider": PROVIDER_EVENTS,
    "record": RECORD_EVENTS,
    "reports": REPORTS_EVENTS,
    "rubric": RUBRIC_EVENTS,
    "scenario": SCENARIO_EVENTS,
    "session": SESSION_EVENTS,
    "setting": SETTING_EVENTS,
    "simulation": SIMULATION_EVENTS,
    "test": TEST_EVENTS,
    "tool": TOOL_EVENTS,
}


def get_artifact_events_config(artifact: str) -> ArtifactEventsConfig | None:
    """Resolve the event declaration bundle for an artifact."""
    return EVENT_REGISTRY.get(artifact)
