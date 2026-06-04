"""Session operation event configs (contributed to the ``system`` parent).

Post 19→3 consolidation, session is nested under the ``system`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.session.types import (
    GetSessionDetailRequest,
    GetSessionDetailResponse,
)

SESSION_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    # HTTP route emits operation="session"; WS handler emits "session_get".
    # Register both keys so neither emitter is orphaned (both project).
    "session": OperationEventConfig(
        operation="session",
        scope="entity",
        entity_key="session_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetSessionDetailRequest,
            "completed": GetSessionDetailResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"system.session_viewed": None},
    ),
    "session_get": OperationEventConfig(
        operation="session_get",
        scope="entity",
        entity_key="session_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetSessionDetailRequest,
            "completed": GetSessionDetailResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"system.session_viewed": None},
    ),
    "session_refresh": OperationEventConfig(
        operation="session_refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"system.session_refreshed": None},
    ),
}
