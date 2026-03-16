"""Reports event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationEventConfig,
    require_authenticated_profile,
)

REPORTS_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.reports.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

REPORTS_EVENTS = ArtifactEventsConfig(
    artifact="reports",
    operations=REPORTS_EVENT_CONFIGS,
)


def get_reports_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a reports operation."""
    return REPORTS_EVENTS.get_operation(operation)
