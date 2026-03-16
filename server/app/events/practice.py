"""Practice event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.practice.types import (
    GetPracticeRequest,
    GetPracticeResponse,
)

PRACTICE_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetPracticeRequest,
            "completed": GetPracticeResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.practice.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.practice.refreshed": None},
    ),
}

PRACTICE_EVENTS = ArtifactEventsConfig(
    artifact="practice",
    operations=PRACTICE_EVENT_CONFIGS,
)


def get_practice_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a practice operation."""
    return PRACTICE_EVENTS.get_operation(operation)
