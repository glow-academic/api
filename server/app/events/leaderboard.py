"""Leaderboard event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.leaderboard.types import (
    LeaderboardRequest,
    LeaderboardResponse,
)

LEADERBOARD_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": LeaderboardRequest,
            "completed": LeaderboardResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.leaderboard.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.leaderboard.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

LEADERBOARD_EVENTS = ArtifactEventsConfig(
    artifact="leaderboard",
    operations=LEADERBOARD_EVENT_CONFIGS,
)


def get_leaderboard_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a leaderboard operation."""
    return LEADERBOARD_EVENTS.get_operation(operation)
