"""Central registry for artifact event declarations.

Post 19→3 consolidation, satellite artifacts (chat/record/practice/home/
reports/dashboard/leaderboard, benchmark/invocation, activity/group/health/
session) no longer appear as top-level registry keys — their operation configs
are merged into their respective parent artifacts (attempt / test / system).
"""

from __future__ import annotations

from app.events.agent import AGENT_EVENTS
from app.events.attempt import ATTEMPT_EVENTS
from app.events.auth import AUTH_EVENTS
from app.events.cohort import COHORT_EVENTS
from app.events.department import DEPARTMENT_EVENTS
from app.events.document import DOCUMENT_EVENTS
from app.events.eval import EVAL_EVENTS
from app.events.field import FIELD_EVENTS
from app.events.model import MODEL_EVENTS
from app.events.parameter import PARAMETER_EVENTS
from app.events.persona import PERSONA_EVENTS
from app.events.pricing import PRICING_EVENTS
from app.events.profile import PROFILE_EVENTS
from app.events.provider import PROVIDER_EVENTS
from app.events.rubric import RUBRIC_EVENTS
from app.events.scenario import SCENARIO_EVENTS
from app.events.setting import SETTING_EVENTS
from app.events.simulation import SIMULATION_EVENTS
from app.events.system import SYSTEM_EVENTS
from app.events.test import TEST_EVENTS
from app.events.tool import TOOL_EVENTS
from app.events.types import ArtifactEventsConfig

EVENT_REGISTRY: dict[str, ArtifactEventsConfig] = {
    "agent": AGENT_EVENTS,
    "attempt": ATTEMPT_EVENTS,
    "auth": AUTH_EVENTS,
    "cohort": COHORT_EVENTS,
    "department": DEPARTMENT_EVENTS,
    "document": DOCUMENT_EVENTS,
    "eval": EVAL_EVENTS,
    "field": FIELD_EVENTS,
    "model": MODEL_EVENTS,
    "parameter": PARAMETER_EVENTS,
    "persona": PERSONA_EVENTS,
    "pricing": PRICING_EVENTS,
    "profile": PROFILE_EVENTS,
    "provider": PROVIDER_EVENTS,
    "rubric": RUBRIC_EVENTS,
    "scenario": SCENARIO_EVENTS,
    "setting": SETTING_EVENTS,
    "simulation": SIMULATION_EVENTS,
    "system": SYSTEM_EVENTS,
    "test": TEST_EVENTS,
    "tool": TOOL_EVENTS,
}


def get_artifact_events_config(artifact: str) -> ArtifactEventsConfig | None:
    """Resolve the event declaration bundle for an artifact."""
    return EVENT_REGISTRY.get(artifact)
