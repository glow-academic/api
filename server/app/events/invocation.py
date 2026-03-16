"""Invocation event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.invocation.types import (
    GetSuiteRequest,
    GetSuiteResponse,
)

INVOCATION_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="test_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetSuiteRequest,
            "completed": GetSuiteResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.invocation.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.invocation.refreshed": None},
    ),
}

INVOCATION_EVENTS = ArtifactEventsConfig(
    artifact="invocation",
    operations=INVOCATION_EVENT_CONFIGS,
)


def get_invocation_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for an invocation operation."""
    return INVOCATION_EVENTS.get_operation(operation)
