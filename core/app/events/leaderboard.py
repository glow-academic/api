"""Leaderboard operation event configs (contributed to the ``attempt`` parent).

Post 19→3 consolidation, leaderboard is nested under the ``attempt`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.leaderboard.types import (
    LeaderboardRequest,
    LeaderboardResponse,
)

LEADERBOARD_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "leaderboard": OperationEventConfig(
        operation="leaderboard",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": LeaderboardRequest,
            "completed": LeaderboardResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"attempt.leaderboard_viewed": None},
    ),
    "leaderboard_refresh": OperationEventConfig(
        operation="leaderboard_refresh",
        domain_events={"attempt.leaderboard_refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}
