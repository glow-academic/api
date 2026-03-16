"""Group event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    default_filter_events,
    require_authenticated_profile,
)
from app.infra.group.types import (
    GetGroupDetailRequest,
    GetGroupDetailResponse,
)
from app.infra.websocket.generation_types import (
    # Generation lifecycle input payload (client → server)
    GeneratePayload,
    # Generation domain event payloads (server → client)
    GenerationCompleteEvent,
    GenerationProgressEvent,
)

GROUP_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="group_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetGroupDetailRequest,
            "completed": GetGroupDetailResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.group.viewed": None,
        },
    ),
    "generate": OperationEventConfig(
        operation="generate",
        scope="entity",
        entity_key="group_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GeneratePayload,
            "completed": GenerationCompleteEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.group.generation.started": GenerationCompleteEvent,
            "artifacts.group.generation.progress": GenerationProgressEvent,
            "artifacts.group.generation.completed": GenerationCompleteEvent,
        },
        filter_events=default_filter_events,
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.group.refreshed": None,
        },
    ),
}

GROUP_EVENTS = ArtifactEventsConfig(
    artifact="group",
    operations=GROUP_EVENT_CONFIGS,
)


def get_group_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a group operation."""
    return GROUP_EVENTS.get_operation(operation)
