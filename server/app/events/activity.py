"""Activity event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.activity.types import (
    ActivityRequest,
    ActivityResponse,
)

ACTIVITY_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ActivityRequest,
            "completed": ActivityResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.activity.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.activity.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

ACTIVITY_EVENTS = ArtifactEventsConfig(
    artifact="activity",
    operations=ACTIVITY_EVENT_CONFIGS,
)


def get_activity_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for an activity operation."""
    return ACTIVITY_EVENTS.get_operation(operation)
