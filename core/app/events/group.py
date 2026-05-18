"""Group operation event configs (contributed to the ``system`` parent).

Post 19→3 consolidation, group is nested under the ``system`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    default_filter_events,
    require_authenticated_profile,
)
from app.infra.group.resolve import (
    GroupResolveRequest as GetGroupDetailRequest,
    GroupResolveResponse as GetGroupDetailResponse,
)
from app.infra.websocket.generation_types import (
    # Generation lifecycle input payload (client → server)
    GeneratePayload,
    # Generation domain event payloads (server → client)
    GenerationCompleteEvent,
    GenerationProgressEvent,
)

GROUP_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "group_get": OperationEventConfig(
        operation="group_get",
        scope="entity",
        entity_key="group_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetGroupDetailRequest,
            "completed": GetGroupDetailResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "system.group_viewed": None,
        },
    ),
    "group_generate": OperationEventConfig(
        operation="group_generate",
        scope="entity",
        entity_key="group_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GeneratePayload,
            "completed": GenerationCompleteEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "system.group_generate.started": GenerationCompleteEvent,
            "system.group_generate.progress": GenerationProgressEvent,
            "system.group_generate.completed": GenerationCompleteEvent,
        },
        filter_events=default_filter_events,
    ),
    "group_refresh": OperationEventConfig(
        operation="group_refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "system.group_refreshed": None,
        },
    ),
}
