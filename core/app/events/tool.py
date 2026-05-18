"""Tool event declarations for centralized delivery."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.tool.types import (
    CreateToolApiRequest,
    CreateToolApiResponse,
    DeleteToolApiRequest,
    DeleteToolApiResponse,
    DuplicateToolApiRequest,
    DuplicateToolApiResponse,
    ExportToolApiRequest,
    ExportToolApiResponse,
    GetToolApiRequest,
    GetToolApiResponse,
    GetToolDraftsApiResponse,
    PatchToolDraftApiRequest,
    PatchToolDraftApiResponse,
    UpdateToolApiRequest,
    UpdateToolApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _tool_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve tool IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("tool_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("tool_id")
        ]
    )


def _tool_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated tool ID from output."""
    del arguments
    return _uuid_list([output.get("tool_id")])


def _tool_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _tool_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


TOOL_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        domain_events={"tool.viewed": None},
        scope="entity",
        entity_key="tool_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetToolApiRequest,
            "completed": GetToolApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _tool_request_entity_ids(
            arguments, output, "tool_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        domain_events={"tool.created": CreateToolApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateToolApiRequest,
            "completed": CreateToolApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_tool_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        domain_events={"tool.updated": UpdateToolApiResponse},
        scope="entity",
        entity_key="tool_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateToolApiRequest,
            "completed": UpdateToolApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_tool_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        domain_events={"tool.deleted": DeleteToolApiResponse},
        scope="entity",
        entity_key="tool_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteToolApiRequest,
            "completed": DeleteToolApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_tool_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        domain_events={"tool.duplicated": DuplicateToolApiResponse},
        scope="entity",
        entity_key="tool_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateToolApiRequest,
            "completed": DuplicateToolApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_tool_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        domain_events={"tool.draft.saved": PatchToolDraftApiResponse},
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchToolDraftApiRequest,
            "completed": PatchToolDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_tool_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        domain_events={"tool.drafts.viewed": GetToolDraftsApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        domain_events={"tool.search.performed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "export": OperationEventConfig(
        operation="export",
        domain_events={"tool.exported": ExportToolApiResponse},
        scope="collection",
        entity_key="tool_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportToolApiRequest,
            "completed": ExportToolApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _tool_request_entity_ids(
            arguments, output, "tool_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"tool.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

TOOL_EVENTS = ArtifactEventsConfig(
    artifact="tool",
    operations=TOOL_EVENT_CONFIGS,
)


def get_tool_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a tool operation."""
    return TOOL_EVENTS.get_operation(operation)
