"""Invocation operation event configs (contributed to the ``test`` parent).

Post 19→3 consolidation, invocation is nested under the ``test`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.invocation.types import (
    GetSuiteRequest,
    GetSuiteResponse,
)

INVOCATION_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "invocation_get": OperationEventConfig(
        operation="invocation_get",
        scope="entity",
        entity_key="test_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetSuiteRequest,
            "completed": GetSuiteResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.test.invocation_viewed": None},
    ),
    "invocation_refresh": OperationEventConfig(
        operation="invocation_refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.test.invocation_refreshed": None},
    ),
}
