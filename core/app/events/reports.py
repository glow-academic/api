"""Reports operation event configs (contributed to the ``attempt`` parent).

Post 19→3 consolidation, reports is nested under the ``attempt`` artifact.
"""

from app.events.types import (
    OperationEventConfig,
    require_authenticated_profile,
)

REPORTS_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "reports_refresh": OperationEventConfig(
        operation="reports_refresh",
        domain_events={"artifacts.attempt.reports_refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}
