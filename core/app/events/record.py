"""Record operation event configs (contributed to the ``attempt`` parent).

Post 19→3 consolidation, record is nested under the ``attempt`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.dashboard.types import DashboardBundleResponse
from app.infra.record.types import RecordRequest

RECORD_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "record_get": OperationEventConfig(
        operation="record_get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": RecordRequest,
            "completed": DashboardBundleResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.attempt.record_viewed": None},
    ),
    "record_refresh": OperationEventConfig(
        operation="record_refresh",
        domain_events={"artifacts.attempt.record_refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}
