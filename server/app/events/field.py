"""Field event declarations for centralized delivery."""

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
from app.infra.field.types import (
    CreateFieldApiRequest,
    CreateFieldApiResponse,
    DeleteFieldApiRequest,
    DeleteFieldApiResponse,
    DuplicateFieldApiRequest,
    DuplicateFieldApiResponse,
    ExportFieldApiRequest,
    ExportFieldApiResponse,
    GetFieldApiRequest,
    GetFieldApiResponse,
    GetFieldDraftsApiResponse,
    PatchFieldDraftApiRequest,
    PatchFieldDraftApiResponse,
    UpdateFieldApiRequest,
    UpdateFieldApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _field_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve field IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("field_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("field_id")
        ]
    )


def _field_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated field ID from output."""
    del arguments
    return _uuid_list([output.get("field_id")])


def _field_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _field_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


FIELD_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        domain_events={"artifacts.field.viewed": None},
        scope="entity",
        entity_key="field_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetFieldApiRequest,
            "completed": GetFieldApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _field_request_entity_ids(
            arguments, output, "field_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        domain_events={"artifacts.field.created": CreateFieldApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateFieldApiRequest,
            "completed": CreateFieldApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_field_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        domain_events={"artifacts.field.updated": UpdateFieldApiResponse},
        scope="entity",
        entity_key="field_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateFieldApiRequest,
            "completed": UpdateFieldApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_field_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        domain_events={"artifacts.field.deleted": DeleteFieldApiResponse},
        scope="entity",
        entity_key="field_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteFieldApiRequest,
            "completed": DeleteFieldApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_field_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        domain_events={"artifacts.field.duplicated": DuplicateFieldApiResponse},
        scope="entity",
        entity_key="field_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateFieldApiRequest,
            "completed": DuplicateFieldApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_field_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        domain_events={"artifacts.field.draft.saved": PatchFieldDraftApiResponse},
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchFieldDraftApiRequest,
            "completed": PatchFieldDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_field_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        domain_events={"artifacts.field.drafts.viewed": GetFieldDraftsApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        domain_events={"artifacts.field.search.performed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "docs": OperationEventConfig(
        operation="docs",
        domain_events={"artifacts.field.docs.viewed": None},
        scope="entity",
        entity_key="entity_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ComposedDocsResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _field_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        domain_events={"artifacts.field.exported": ExportFieldApiResponse},
        scope="collection",
        entity_key="field_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportFieldApiRequest,
            "completed": ExportFieldApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _field_request_entity_ids(
            arguments, output, "field_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.field.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

FIELD_EVENTS = ArtifactEventsConfig(
    artifact="field",
    operations=FIELD_EVENT_CONFIGS,
)


def get_field_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a field operation."""
    return FIELD_EVENTS.get_operation(operation)
