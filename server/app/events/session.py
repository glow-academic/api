"""Session event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.session.types import (
    GetSessionDetailRequest,
    GetSessionDetailResponse,
)

SESSION_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="session_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetSessionDetailRequest,
            "completed": GetSessionDetailResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.session.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.session.refreshed": None},
    ),
}

SESSION_EVENTS = ArtifactEventsConfig(
    artifact="session",
    operations=SESSION_EVENT_CONFIGS,
)


def get_session_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a session operation."""
    return SESSION_EVENTS.get_operation(operation)
