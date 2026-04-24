"""Attempt event declarations for centralized delivery.

Post 19→3 consolidation, the following pre-consolidation satellite artifacts
are nested under ``attempt`` and contribute their operations here:
  - chat, record, practice, home, reports, dashboard, leaderboard

Each satellite event module exposes an ``<NAME>_OPERATION_CONFIGS`` dict keyed
by the canonical underscored operation name (e.g. ``chat_get``, ``home_refresh``)
that this file merges into ``ATTEMPT_EVENT_CONFIGS``.
"""

from app.events.chat import CHAT_OPERATION_CONFIGS
from app.events.dashboard import DASHBOARD_OPERATION_CONFIGS
from app.events.home import HOME_OPERATION_CONFIGS
from app.events.leaderboard import LEADERBOARD_OPERATION_CONFIGS
from app.events.practice import PRACTICE_OPERATION_CONFIGS
from app.events.record import RECORD_OPERATION_CONFIGS
from app.events.reports import REPORTS_OPERATION_CONFIGS
from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    default_filter_events,
    require_authenticated_profile,
)
from app.infra.attempt.client_types import (
    # Attempt domain event payloads (server → client)
    AttemptAssistantCompleteEvent,
    AttemptAssistantProgressEvent,
    AttemptAssistantStartEvent,
    AttemptAudioEndedEvent,
    AttemptAudioReadyEvent,
    # Attempt lifecycle input payloads (client → server)
    AttemptAudioStartPayload,
    AttemptChatEndedEvent,
    AttemptChatStartedEvent,
    AttemptEndedEvent,
    AttemptEndPayload,
    AttemptGradeCompleteEvent,
    AttemptGradePayload,
    AttemptGradeProgressEvent,
    AttemptGradeStartEvent,
    AttemptMessagePayload,
    AttemptResponsePayload,
    AttemptResponseResultEvent,
    AttemptStartedEvent,
    AttemptStartPayload,
    AttemptStopPayload,
    AttemptStoppedEvent,
)
from app.infra.attempt.types import (
    GetAttemptDetailRequest,
    GetAttemptDetailResponse,
)


def _resolve_attempt_start_entity_ids(arguments: dict, output: dict) -> list:
    attempt_id = output.get("attempt_id")
    if not attempt_id:
        return []
    from uuid import UUID

    return [UUID(str(attempt_id))]

ATTEMPT_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="attempt_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetAttemptDetailRequest,
            "completed": GetAttemptDetailResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.viewed": None,
        },
    ),
    "start": OperationEventConfig(
        operation="start",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        resolve_entity_ids=_resolve_attempt_start_entity_ids,
        lifecycle_models={
            "started": AttemptStartPayload,
            "completed": AttemptStartedEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.started": AttemptStartedEvent,
            "artifacts.attempt.chat.started": AttemptChatStartedEvent,
        },
    ),
    "message": OperationEventConfig(
        operation="message",
        scope="entity",
        entity_key="chat_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": AttemptMessagePayload,
            "completed": AttemptAssistantCompleteEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.chat.assistant.start": AttemptAssistantStartEvent,
            "artifacts.attempt.chat.assistant.progress": AttemptAssistantProgressEvent,
            "artifacts.attempt.chat.assistant.complete": AttemptAssistantCompleteEvent,
        },
        filter_events=default_filter_events,
    ),
    "grade": OperationEventConfig(
        operation="grade",
        scope="entity",
        entity_key="attempt_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": AttemptGradePayload,
            "completed": AttemptGradeCompleteEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.chat.grade.start": AttemptGradeStartEvent,
            "artifacts.attempt.chat.grade.progress": AttemptGradeProgressEvent,
            "artifacts.attempt.chat.grade.complete": AttemptGradeCompleteEvent,
        },
        filter_events=default_filter_events,
    ),
    "end": OperationEventConfig(
        operation="end",
        scope="entity",
        entity_key="attempt_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": AttemptEndPayload,
            "completed": AttemptEndedEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.ended": AttemptEndedEvent,
            "artifacts.attempt.chat.ended": AttemptChatEndedEvent,
        },
    ),
    "response": OperationEventConfig(
        operation="response",
        scope="entity",
        entity_key="attempt_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": AttemptResponsePayload,
            "completed": AttemptResponseResultEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.chat.response.saved": AttemptResponseResultEvent,
        },
    ),
    "stop": OperationEventConfig(
        operation="stop",
        scope="entity",
        entity_key="chat_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": AttemptStopPayload,
            "completed": AttemptStoppedEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.chat.stopped": AttemptStoppedEvent,
        },
    ),
    "chat_voice": OperationEventConfig(
        operation="chat_voice",
        scope="entity",
        entity_key="attempt_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": AttemptAudioStartPayload,
            "completed": AttemptAudioReadyEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.chat.voice.start": AttemptAudioReadyEvent,
            "artifacts.attempt.chat.voice.progress": AttemptAssistantProgressEvent,
        },
        filter_events=default_filter_events,
    ),
    "chat_silence": OperationEventConfig(
        operation="chat_silence",
        scope="entity",
        entity_key="chat_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "completed": AttemptAudioEndedEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.chat.voice.complete": AttemptAudioEndedEvent,
        },
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.attempt.refreshed": None,
        },
    ),
}

# Merge in the satellite operation configs. Native attempt ops win collisions.
_MERGED_ATTEMPT_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    **CHAT_OPERATION_CONFIGS,
    **RECORD_OPERATION_CONFIGS,
    **PRACTICE_OPERATION_CONFIGS,
    **HOME_OPERATION_CONFIGS,
    **REPORTS_OPERATION_CONFIGS,
    **DASHBOARD_OPERATION_CONFIGS,
    **LEADERBOARD_OPERATION_CONFIGS,
    **ATTEMPT_EVENT_CONFIGS,
}

ATTEMPT_EVENTS = ArtifactEventsConfig(
    artifact="attempt",
    operations=_MERGED_ATTEMPT_EVENT_CONFIGS,
)


def get_attempt_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for an attempt operation."""
    return ATTEMPT_EVENTS.get_operation(operation)
