"""Practice operation event configs (contributed to the ``attempt`` parent).

Post 19→3 consolidation, practice is nested under the ``attempt`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.practice.types import (
    GetPracticeRequest,
    GetPracticeResponse,
)

PRACTICE_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "practice": OperationEventConfig(
        operation="practice",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetPracticeRequest,
            "completed": GetPracticeResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"attempt.practice_viewed": None},
    ),
    "practice_refresh": OperationEventConfig(
        operation="practice_refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"attempt.practice_refreshed": None},
    ),
}
