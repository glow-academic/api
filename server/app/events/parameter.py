"""Parameter event declarations for centralized delivery."""

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
from app.infra.parameter.types import (
    CreateParameterApiRequest,
    CreateParameterApiResponse,
    DeleteParameterApiRequest,
    DeleteParameterApiResponse,
    DuplicateParameterApiRequest,
    DuplicateParameterApiResponse,
    ExportParameterApiRequest,
    ExportParameterApiResponse,
    GetParameterApiRequest,
    GetParameterApiResponse,
    GetParameterDraftsApiResponse,
    PatchParameterDraftApiRequest,
    PatchParameterDraftApiResponse,
    UpdateParameterApiRequest,
    UpdateParameterApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _parameter_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve parameter IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("parameter_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("parameter_id")
        ]
    )


def _parameter_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated parameter ID from output."""
    del arguments
    return _uuid_list([output.get("parameter_id")])


def _parameter_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _parameter_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


PARAMETER_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        domain_events={"artifacts.parameter.viewed": None},
        scope="entity",
        entity_key="parameter_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetParameterApiRequest,
            "completed": GetParameterApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _parameter_request_entity_ids(
            arguments, output, "parameter_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        domain_events={"artifacts.parameter.created": CreateParameterApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateParameterApiRequest,
            "completed": CreateParameterApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_parameter_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        domain_events={"artifacts.parameter.updated": UpdateParameterApiResponse},
        scope="entity",
        entity_key="parameter_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateParameterApiRequest,
            "completed": UpdateParameterApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_parameter_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        domain_events={"artifacts.parameter.deleted": DeleteParameterApiResponse},
        scope="entity",
        entity_key="parameter_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteParameterApiRequest,
            "completed": DeleteParameterApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_parameter_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        domain_events={
            "artifacts.parameter.duplicated": DuplicateParameterApiResponse,
        },
        scope="entity",
        entity_key="parameter_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateParameterApiRequest,
            "completed": DuplicateParameterApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_parameter_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        domain_events={
            "artifacts.parameter.draft.saved": PatchParameterDraftApiResponse,
        },
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchParameterDraftApiRequest,
            "completed": PatchParameterDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_parameter_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        domain_events={
            "artifacts.parameter.drafts.viewed": GetParameterDraftsApiResponse,
        },
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        domain_events={"artifacts.parameter.search.performed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "docs": OperationEventConfig(
        operation="docs",
        domain_events={"artifacts.parameter.docs.viewed": None},
        scope="entity",
        entity_key="entity_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ComposedDocsResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _parameter_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        domain_events={"artifacts.parameter.exported": ExportParameterApiResponse},
        scope="collection",
        entity_key="parameter_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportParameterApiRequest,
            "completed": ExportParameterApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _parameter_request_entity_ids(
            arguments, output, "parameter_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.parameter.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

PARAMETER_EVENTS = ArtifactEventsConfig(
    artifact="parameter",
    operations=PARAMETER_EVENT_CONFIGS,
)


def get_parameter_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a parameter operation."""
    return PARAMETER_EVENTS.get_operation(operation)
