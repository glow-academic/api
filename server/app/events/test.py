"""Test event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    default_filter_events,
    require_authenticated_profile,
)
from app.infra.test.types import (
    GetTestArtifactRequest,
    GetTestArtifactResponse,
)
from app.infra.test.client_types import (
    # Test domain event payloads (server → client)
    TestAllCompleteEvent,
    # Test lifecycle input payloads (client → server)
    TestEndPayload,
    TestProgressEvent,
    TestRunCompleteEvent,
    TestRunStartEvent,
    TestStartedEvent,
    TestStartPayload,
    TestStopPayload,
    TestStoppedEvent,
)

TEST_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="test_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetTestArtifactRequest,
            "completed": GetTestArtifactResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.test.viewed": None,
        },
    ),
    "start": OperationEventConfig(
        operation="start",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": TestStartPayload,
            "completed": TestStartedEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.test.started": TestStartedEvent,
        },
    ),
    "run": OperationEventConfig(
        operation="run",
        scope="entity",
        entity_key="invocation_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": TestRunStartEvent,
            "completed": TestRunCompleteEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.test.run.replay_started": TestRunStartEvent,
            "artifacts.test.run.progress": TestProgressEvent,
            "artifacts.test.run.replay_completed": TestRunCompleteEvent,
        },
        filter_events=default_filter_events,
    ),
    "end": OperationEventConfig(
        operation="end",
        scope="entity",
        entity_key="invocation_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": TestEndPayload,
            "completed": TestAllCompleteEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.test.ended": TestAllCompleteEvent,
        },
    ),
    "stop": OperationEventConfig(
        operation="stop",
        scope="entity",
        entity_key="invocation_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": TestStopPayload,
            "completed": TestStoppedEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.test.stopped": TestStoppedEvent,
        },
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.test.refreshed": None,
        },
    ),
}

TEST_EVENTS = ArtifactEventsConfig(
    artifact="test",
    operations=TEST_EVENT_CONFIGS,
)


def get_test_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a test operation."""
    return TEST_EVENTS.get_operation(operation)
