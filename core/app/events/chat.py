"""Chat operation event configs (contributed to the ``attempt`` parent).

Post 19→3 consolidation, chat is nested under the ``attempt`` artifact. This
module no longer exports an ``ArtifactEventsConfig`` — it exposes a dict of
``OperationEventConfig`` keyed by the canonical ``chat_<op>`` form that
``app.events.attempt`` merges into ``ATTEMPT_EVENT_CONFIGS``.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.attempt.chat.types import (
    GetChatRequest,
    GetChatResponse,
)

CHAT_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "chat_get": OperationEventConfig(
        operation="chat_get",
        scope="entity",
        entity_key="chat_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetChatRequest,
            "completed": GetChatResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.attempt.chat_viewed": None},
    ),
    "chat_refresh": OperationEventConfig(
        operation="chat_refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.attempt.chat_refreshed": None},
    ),
}
