"""Model event declarations for centralized delivery."""

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
from app.infra.model.types import (
    CreateModelApiRequest,
    CreateModelApiResponse,
    DeleteModelApiRequest,
    DeleteModelApiResponse,
    DuplicateModelApiRequest,
    DuplicateModelApiResponse,
    ExportModelApiRequest,
    ExportModelApiResponse,
    GetModelApiRequest,
    GetModelApiResponse,
    GetModelDraftsApiResponse,
    PatchModelDraftApiRequest,
    PatchModelDraftApiResponse,
    UpdateModelApiRequest,
    UpdateModelApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _model_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve model IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("model_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("model_id")
        ]
    )


def _model_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated model ID from output."""
    del arguments
    return _uuid_list([output.get("model_id")])


def _model_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _model_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


MODEL_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        domain_events={"artifacts.model.viewed": None},
        scope="entity",
        entity_key="model_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetModelApiRequest,
            "completed": GetModelApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _model_request_entity_ids(
            arguments, output, "model_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        domain_events={"artifacts.model.created": CreateModelApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateModelApiRequest,
            "completed": CreateModelApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_model_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        domain_events={"artifacts.model.updated": UpdateModelApiResponse},
        scope="entity",
        entity_key="model_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateModelApiRequest,
            "completed": UpdateModelApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_model_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        domain_events={"artifacts.model.deleted": DeleteModelApiResponse},
        scope="entity",
        entity_key="model_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteModelApiRequest,
            "completed": DeleteModelApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_model_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        domain_events={"artifacts.model.duplicated": DuplicateModelApiResponse},
        scope="entity",
        entity_key="model_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateModelApiRequest,
            "completed": DuplicateModelApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_model_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        domain_events={"artifacts.model.draft.saved": PatchModelDraftApiResponse},
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchModelDraftApiRequest,
            "completed": PatchModelDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_model_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        domain_events={"artifacts.model.drafts.viewed": GetModelDraftsApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        domain_events={"artifacts.model.search.performed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "docs": OperationEventConfig(
        operation="docs",
        domain_events={"artifacts.model.docs.viewed": None},
        scope="entity",
        entity_key="entity_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ComposedDocsResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _model_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        domain_events={"artifacts.model.exported": ExportModelApiResponse},
        scope="collection",
        entity_key="model_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportModelApiRequest,
            "completed": ExportModelApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _model_request_entity_ids(
            arguments, output, "model_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.model.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

MODEL_EVENTS = ArtifactEventsConfig(
    artifact="model",
    operations=MODEL_EVENT_CONFIGS,
)


def get_model_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a model operation."""
    return MODEL_EVENTS.get_operation(operation)
