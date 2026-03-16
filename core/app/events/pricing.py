"""Pricing event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.pricing.types import PricingRequest, PricingResponse

PRICING_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PricingRequest,
            "completed": PricingResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.pricing.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.pricing.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

PRICING_EVENTS = ArtifactEventsConfig(
    artifact="pricing",
    operations=PRICING_EVENT_CONFIGS,
)


def get_pricing_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a pricing operation."""
    return PRICING_EVENTS.get_operation(operation)
