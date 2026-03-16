"""Rubric event declarations for centralized delivery."""

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
from app.infra.rubric.types import (
    CreateRubricApiRequest,
    CreateRubricApiResponse,
    DeleteRubricApiRequest,
    DeleteRubricApiResponse,
    DuplicateRubricApiRequest,
    DuplicateRubricApiResponse,
    ExportRubricApiResponse,
    GetRubricApiRequest,
    GetRubricApiResponse,
    GetRubricDraftsApiResponse,
    PatchRubricDraftApiRequest,
    PatchRubricDraftApiResponse,
    UpdateRubricApiRequest,
    UpdateRubricApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _rubric_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve rubric IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("rubric_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("rubric_id")
        ]
    )


def _rubric_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated rubric ID from output."""
    del arguments
    return _uuid_list([output.get("rubric_id")])


def _rubric_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _rubric_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


RUBRIC_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="rubric_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetRubricApiRequest,
            "completed": GetRubricApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.rubric.viewed": None},
        resolve_entity_ids=lambda arguments, output: _rubric_request_entity_ids(
            arguments, output, "rubric_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateRubricApiRequest,
            "completed": CreateRubricApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.rubric.created": CreateRubricApiResponse},
        resolve_entity_ids=_rubric_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        scope="entity",
        entity_key="rubric_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateRubricApiRequest,
            "completed": UpdateRubricApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.rubric.updated": UpdateRubricApiResponse},
        resolve_entity_ids=_rubric_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        scope="entity",
        entity_key="rubric_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteRubricApiRequest,
            "completed": DeleteRubricApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.rubric.deleted": DeleteRubricApiResponse},
        resolve_entity_ids=_rubric_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        scope="entity",
        entity_key="rubric_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateRubricApiRequest,
            "completed": DuplicateRubricApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.rubric.duplicated": DuplicateRubricApiResponse},
        resolve_entity_ids=_rubric_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchRubricDraftApiRequest,
            "completed": PatchRubricDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.rubric.draft.saved": PatchRubricDraftApiResponse,
        },
        resolve_entity_ids=_rubric_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.rubric.drafts.viewed": GetRubricDraftsApiResponse,
        },
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.rubric.search.performed": None},
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
        domain_events={"artifacts.rubric.docs.viewed": None},
        resolve_entity_ids=lambda arguments, output: _rubric_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        scope="collection",
        entity_key="rubric_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ExportRubricApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.rubric.exported": ExportRubricApiResponse},
        resolve_entity_ids=lambda arguments, output: _rubric_request_entity_ids(
            arguments, output, "rubric_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.rubric.refreshed": None},
    ),
}

RUBRIC_EVENTS = ArtifactEventsConfig(
    artifact="rubric",
    operations=RUBRIC_EVENT_CONFIGS,
)


def get_rubric_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a rubric operation."""
    return RUBRIC_EVENTS.get_operation(operation)
