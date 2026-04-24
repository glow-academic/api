"""System event declarations for centralized delivery.

Post 19→3 consolidation, the following pre-consolidation satellite artifacts
are nested under ``system`` and contribute their operations here:
  - activity, group, health, session
"""

from app.events.activity import ACTIVITY_OPERATION_CONFIGS
from app.events.group import GROUP_OPERATION_CONFIGS
from app.events.health import HEALTH_OPERATION_CONFIGS
from app.events.session import SESSION_OPERATION_CONFIGS
from app.events.types import (
    ArtifactEventsConfig,
    OperationEventConfig,
)

SYSTEM_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    **ACTIVITY_OPERATION_CONFIGS,
    **GROUP_OPERATION_CONFIGS,
    **HEALTH_OPERATION_CONFIGS,
    **SESSION_OPERATION_CONFIGS,
}

SYSTEM_EVENTS = ArtifactEventsConfig(
    artifact="system",
    operations=SYSTEM_EVENT_CONFIGS,
)


def get_system_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a system operation."""
    return SYSTEM_EVENTS.get_operation(operation)
