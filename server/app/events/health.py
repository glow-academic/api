"""Health event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.health.types import HealthRequest, HealthResponse

HEALTH_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": HealthRequest,
            "completed": HealthResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.health.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.health.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

HEALTH_EVENTS = ArtifactEventsConfig(
    artifact="health",
    operations=HEALTH_EVENT_CONFIGS,
)


def get_health_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a health operation."""
    return HEALTH_EVENTS.get_operation(operation)
