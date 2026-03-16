"""Record event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.dashboard.types import DashboardBundleResponse
from app.infra.record.types import RecordRequest

RECORD_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": RecordRequest,
            "completed": DashboardBundleResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.record.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.record.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

RECORD_EVENTS = ArtifactEventsConfig(
    artifact="record",
    operations=RECORD_EVENT_CONFIGS,
)


def get_record_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a record operation."""
    return RECORD_EVENTS.get_operation(operation)
