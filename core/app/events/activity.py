"""Activity operation event configs (contributed to the ``system`` parent).

Post 19→3 consolidation, activity is nested under the ``system`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.activity.types import (
    ActivityRequest,
    ActivityResponse,
)

ACTIVITY_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "activity": OperationEventConfig(
        operation="activity",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ActivityRequest,
            "completed": ActivityResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"system.activity_viewed": None},
    ),
    "activity_refresh": OperationEventConfig(
        operation="activity_refresh",
        domain_events={"system.activity_refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}
