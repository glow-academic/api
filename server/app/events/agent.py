"""Agent event declarations for centralized delivery."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.docs.types import ComposedDocsResponse
from app.infra.agent.types import (
    CreateAgentApiRequest,
    CreateAgentApiResponse,
    DeleteAgentApiRequest,
    DeleteAgentApiResponse,
    DuplicateAgentApiRequest,
    DuplicateAgentApiResponse,
    ExportAgentApiRequest,
    ExportAgentApiResponse,
    GetAgentApiRequest,
    GetAgentApiResponse,
    GetAgentDraftsApiResponse,
    PatchAgentDraftApiRequest,
    PatchAgentDraftApiResponse,
    UpdateAgentApiRequest,
    UpdateAgentApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _agent_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve agent IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("agent_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("agent_id")
        ]
    )


def _agent_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated agent ID from output."""
    del arguments
    return _uuid_list([output.get("agent_id")])


def _agent_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _agent_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


AGENT_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="agent_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetAgentApiRequest,
            "completed": GetAgentApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.agent.viewed": None},
        resolve_entity_ids=lambda arguments, output: _agent_request_entity_ids(
            arguments, output, "agent_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateAgentApiRequest,
            "completed": CreateAgentApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.agent.created": CreateAgentApiResponse},
        resolve_entity_ids=_agent_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        scope="entity",
        entity_key="agent_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateAgentApiRequest,
            "completed": UpdateAgentApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.agent.updated": UpdateAgentApiResponse},
        resolve_entity_ids=_agent_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        scope="entity",
        entity_key="agent_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteAgentApiRequest,
            "completed": DeleteAgentApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.agent.deleted": DeleteAgentApiResponse},
        resolve_entity_ids=_agent_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        scope="entity",
        entity_key="agent_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateAgentApiRequest,
            "completed": DuplicateAgentApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.agent.duplicated": DuplicateAgentApiResponse},
        resolve_entity_ids=_agent_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchAgentDraftApiRequest,
            "completed": PatchAgentDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.agent.draft.saved": PatchAgentDraftApiResponse},
        resolve_entity_ids=_agent_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.agent.drafts.viewed": GetAgentDraftsApiResponse},
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.agent.search.performed": None},
        include_call_lifecycle=False,
    ),
    "docs": OperationEventConfig(
        operation="docs",
        scope="entity",
        entity_key="entity_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ComposedDocsResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.agent.docs.viewed": None},
        resolve_entity_ids=lambda arguments, output: _agent_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        scope="collection",
        entity_key="agent_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportAgentApiRequest,
            "completed": ExportAgentApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.agent.exported": ExportAgentApiResponse},
        resolve_entity_ids=lambda arguments, output: _agent_request_entity_ids(
            arguments, output, "agent_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.agent.refreshed": None},
    ),
}

AGENT_EVENTS = ArtifactEventsConfig(
    artifact="agent",
    operations=AGENT_EVENT_CONFIGS,
)


def get_agent_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for an agent operation."""
    return AGENT_EVENTS.get_operation(operation)
