"""Home operation event configs (contributed to the ``attempt`` parent).

Post 19→3 consolidation, home is nested under the ``attempt`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.home.types import GetHomeRequest, GetHomeResponse

HOME_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "home": OperationEventConfig(
        operation="home",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetHomeRequest,
            "completed": GetHomeResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"attempt.home_viewed": None},
    ),
    # WS handler (ws/attempt/home/get.py) emits operation="home_get"; the HTTP
    # route emits bare "home". Register both so neither emitter is orphaned.
    "home_get": OperationEventConfig(
        operation="home_get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetHomeRequest,
            "completed": GetHomeResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"attempt.home_viewed": None},
    ),
    "home_refresh": OperationEventConfig(
        operation="home_refresh",
        domain_events={"attempt.home_refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}
