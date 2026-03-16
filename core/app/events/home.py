"""Home event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.home.types import GetHomeRequest, GetHomeResponse

HOME_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetHomeRequest,
            "completed": GetHomeResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.home.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.home.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

HOME_EVENTS = ArtifactEventsConfig(
    artifact="home",
    operations=HOME_EVENT_CONFIGS,
)


def get_home_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a home operation."""
    return HOME_EVENTS.get_operation(operation)
