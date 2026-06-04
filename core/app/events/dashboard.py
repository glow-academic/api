"""Dashboard operation event configs (contributed to the ``attempt`` parent).

Post 19→3 consolidation, dashboard is nested under the ``attempt`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.dashboard.types import (
    DashboardBundleResponse,
    DashboardRequest,
)

DASHBOARD_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "dashboard": OperationEventConfig(
        operation="dashboard",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DashboardRequest,
            "completed": DashboardBundleResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"attempt.dashboard_viewed": None},
    ),
    # WS handler (ws/attempt/dashboard/get.py) emits operation="dashboard_get";
    # the HTTP route emits bare "dashboard". Register both (neither orphaned).
    "dashboard_get": OperationEventConfig(
        operation="dashboard_get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DashboardRequest,
            "completed": DashboardBundleResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"attempt.dashboard_viewed": None},
    ),
    "dashboard_refresh": OperationEventConfig(
        operation="dashboard_refresh",
        domain_events={"attempt.dashboard_refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}
