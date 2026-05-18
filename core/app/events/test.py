"""Test event declarations for centralized delivery.

Post 19→3 consolidation, the following pre-consolidation satellite artifacts
are nested under ``test`` and contribute their operations here:
  - benchmark, invocation
"""

from app.events.benchmark import BENCHMARK_OPERATION_CONFIGS
from app.events.invocation import INVOCATION_OPERATION_CONFIGS
from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    default_filter_events,
    require_authenticated_profile,
)
from app.infra.test.client_types import (
    # Test domain event payloads (server → client)
    TestAllCompleteEvent,
    TestCompletePayload,
    # Test lifecycle input payloads (client → server)
    TestInvocationCompletePayload,
    TestInvocationEndedEvent,
    TestInvocationResponseSavedEvent,
    TestInvocationStartedEvent,
    TestInvocationStoppedEvent,
    TestProgressEvent,
    TestRunCompleteEvent,
    TestRunStartEvent,
    TestStartedEvent,
    TestStartPayload,
    TestStopPayload,
    TestStoppedEvent,
)
from app.infra.test.types import (
    GetTestArtifactRequest,
    GetTestArtifactResponse,
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
            "test.viewed": None,
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
            "test.started": TestStartedEvent,
            "test.invocation.started": TestInvocationStartedEvent,
        },
    ),
    "invocation_create": OperationEventConfig(
        operation="invocation_create",
        scope="entity",
        entity_key="test_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        domain_events={
            "test.invocation.created": TestInvocationStartedEvent,
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
            "test.run.replay_started": TestRunStartEvent,
            "test.run.progress": TestProgressEvent,
            "test.run.replay_completed": TestRunCompleteEvent,
            "test.invocation.response.saved": TestInvocationResponseSavedEvent,
        },
        filter_events=default_filter_events,
    ),
    "complete": OperationEventConfig(
        operation="complete",
        scope="entity",
        entity_key="test_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": TestCompletePayload,
            "completed": TestAllCompleteEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "test.completed": TestAllCompleteEvent,
        },
    ),
    "invocation_complete": OperationEventConfig(
        operation="invocation_complete",
        scope="entity",
        entity_key="invocation_id",
        can_subscribe=require_authenticated_profile,
        project_domain_from_audit=False,
        lifecycle_models={
            "started": TestInvocationCompletePayload,
            "completed": TestInvocationEndedEvent,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "test.invocation.completed": TestInvocationEndedEvent,
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
            "test.invocation.stopped": TestInvocationStoppedEvent,
        },
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "test.refreshed": None,
        },
    ),
}

# Merge in the satellite operation configs. Native test ops win collisions.
_MERGED_TEST_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    **BENCHMARK_OPERATION_CONFIGS,
    **INVOCATION_OPERATION_CONFIGS,
    **TEST_EVENT_CONFIGS,
}

TEST_EVENTS = ArtifactEventsConfig(
    artifact="test",
    operations=_MERGED_TEST_EVENT_CONFIGS,
)


def get_test_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a test operation."""
    return TEST_EVENTS.get_operation(operation)
