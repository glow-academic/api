"""Document event declarations for centralized delivery."""

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
from app.infra.document.types import (
    CreateDocumentApiRequest,
    CreateDocumentApiResponse,
    DeleteDocumentApiRequest,
    DeleteDocumentApiResponse,
    DuplicateDocumentApiRequest,
    DuplicateDocumentApiResponse,
    ExportDocumentApiRequest,
    ExportDocumentApiResponse,
    GetDocumentApiRequest,
    GetDocumentApiResponse,
    GetDocumentDraftsApiResponse,
    PatchDocumentDraftApiRequest,
    PatchDocumentDraftApiResponse,
    UpdateDocumentApiRequest,
    UpdateDocumentApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _document_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve document IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("document_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("document_id")
        ]
    )


def _document_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated document ID from output."""
    del arguments
    return _uuid_list([output.get("document_id")])


def _document_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _document_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


DOCUMENT_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        domain_events={"artifacts.document.viewed": None},
        scope="entity",
        entity_key="document_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetDocumentApiRequest,
            "completed": GetDocumentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _document_request_entity_ids(
            arguments, output, "document_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        domain_events={"artifacts.document.created": CreateDocumentApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateDocumentApiRequest,
            "completed": CreateDocumentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_document_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        domain_events={"artifacts.document.updated": UpdateDocumentApiResponse},
        scope="entity",
        entity_key="document_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateDocumentApiRequest,
            "completed": UpdateDocumentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_document_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        domain_events={"artifacts.document.deleted": DeleteDocumentApiResponse},
        scope="entity",
        entity_key="document_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteDocumentApiRequest,
            "completed": DeleteDocumentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_document_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        domain_events={
            "artifacts.document.duplicated": DuplicateDocumentApiResponse,
        },
        scope="entity",
        entity_key="document_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateDocumentApiRequest,
            "completed": DuplicateDocumentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_document_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        domain_events={
            "artifacts.document.draft.saved": PatchDocumentDraftApiResponse,
        },
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchDocumentDraftApiRequest,
            "completed": PatchDocumentDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_document_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        domain_events={
            "artifacts.document.drafts.viewed": GetDocumentDraftsApiResponse,
        },
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        domain_events={"artifacts.document.search.performed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "docs": OperationEventConfig(
        operation="docs",
        domain_events={"artifacts.document.docs.viewed": None},
        scope="entity",
        entity_key="entity_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ComposedDocsResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _document_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        domain_events={"artifacts.document.exported": ExportDocumentApiResponse},
        scope="collection",
        entity_key="document_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportDocumentApiRequest,
            "completed": ExportDocumentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _document_request_entity_ids(
            arguments, output, "document_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.document.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

DOCUMENT_EVENTS = ArtifactEventsConfig(
    artifact="document",
    operations=DOCUMENT_EVENT_CONFIGS,
)


def get_document_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a document operation."""
    return DOCUMENT_EVENTS.get_operation(operation)
