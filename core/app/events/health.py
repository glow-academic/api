"""Health operation event configs (contributed to the ``system`` parent).

Post 19→3 consolidation, health is nested under the ``system`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.health.types import HealthRequest, HealthResponse

HEALTH_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "health_get": OperationEventConfig(
        operation="health_get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": HealthRequest,
            "completed": HealthResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"system.health_viewed": None},
    ),
    "health_refresh": OperationEventConfig(
        operation="health_refresh",
        domain_events={"system.health_refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}
