"""Attempt event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    default_filter_events,
    require_authenticated_profile,
)
from app.infra.attempt.types import (
    GetAttemptDetailRequest,
    GetAttemptDetailResponse,
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
            "artifacts.attempt.chat_started": AttemptChatStartedEvent,
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
            "artifacts.attempt.assistant.start": AttemptAssistantStartEvent,
            "artifacts.attempt.assistant.progress": AttemptAssistantProgressEvent,
            "artifacts.attempt.assistant.complete": AttemptAssistantCompleteEvent,
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
            "artifacts.attempt.grade.start": AttemptGradeStartEvent,
            "artifacts.attempt.grade.progress": AttemptGradeProgressEvent,
            "artifacts.attempt.grade.complete": AttemptGradeCompleteEvent,
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
            "artifacts.attempt.chat_ended": AttemptChatEndedEvent,
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
            "artifacts.attempt.response.saved": AttemptResponseResultEvent,
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
            "artifacts.attempt.stopped": AttemptStoppedEvent,
        },
    ),
    "audio": OperationEventConfig(
        operation="audio",
        scope="entity",
        entity_key="attempt_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": AttemptAudioStartPayload,
            "completed": AttemptAudioEndedEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.attempt.audio.start": AttemptAudioReadyEvent,
            "artifacts.attempt.audio.progress": AttemptAssistantProgressEvent,
            "artifacts.attempt.audio.complete": AttemptAudioEndedEvent,
        },
        filter_events=default_filter_events,
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

ATTEMPT_EVENTS = ArtifactEventsConfig(
    artifact="attempt",
    operations=ATTEMPT_EVENT_CONFIGS,
)


def get_attempt_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for an attempt operation."""
    return ATTEMPT_EVENTS.get_operation(operation)
