"""Eval event declarations for centralized delivery."""

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
from app.infra.eval.types import (
    CreateEvalApiRequest,
    CreateEvalApiResponse,
    DeleteEvalApiRequest,
    DeleteEvalApiResponse,
    DuplicateEvalApiRequest,
    DuplicateEvalApiResponse,
    ExportEvalApiResponse,
    GetEvalApiRequest,
    GetEvalApiResponse,
    GetEvalDraftsApiResponse,
    PatchEvalDraftApiRequest,
    PatchEvalDraftApiResponse,
    UpdateEvalApiRequest,
    UpdateEvalApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _eval_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve eval IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("eval_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("eval_id")
        ]
    )


def _eval_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated eval ID from output."""
    del arguments
    return _uuid_list([output.get("eval_id")])


def _eval_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _eval_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


EVAL_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="eval_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetEvalApiRequest,
            "completed": GetEvalApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.eval.viewed": None},
        resolve_entity_ids=lambda arguments, output: _eval_request_entity_ids(
            arguments, output, "eval_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateEvalApiRequest,
            "completed": CreateEvalApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.eval.created": CreateEvalApiResponse},
        resolve_entity_ids=_eval_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        scope="entity",
        entity_key="eval_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateEvalApiRequest,
            "completed": UpdateEvalApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.eval.updated": UpdateEvalApiResponse},
        resolve_entity_ids=_eval_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        scope="entity",
        entity_key="eval_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteEvalApiRequest,
            "completed": DeleteEvalApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.eval.deleted": DeleteEvalApiResponse},
        resolve_entity_ids=_eval_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        scope="entity",
        entity_key="eval_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateEvalApiRequest,
            "completed": DuplicateEvalApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.eval.duplicated": DuplicateEvalApiResponse},
        resolve_entity_ids=_eval_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchEvalDraftApiRequest,
            "completed": PatchEvalDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.eval.draft.saved": PatchEvalDraftApiResponse,
        },
        resolve_entity_ids=_eval_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.eval.drafts.viewed": GetEvalDraftsApiResponse,
        },
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.eval.search.performed": None},
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
        domain_events={"artifacts.eval.docs.viewed": None},
        resolve_entity_ids=lambda arguments, output: _eval_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        scope="collection",
        entity_key="eval_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ExportEvalApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.eval.exported": ExportEvalApiResponse},
        resolve_entity_ids=lambda arguments, output: _eval_request_entity_ids(
            arguments, output, "eval_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.eval.refreshed": None},
    ),
}

EVAL_EVENTS = ArtifactEventsConfig(
    artifact="eval",
    operations=EVAL_EVENT_CONFIGS,
)


def get_eval_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for an eval operation."""
    return EVAL_EVENTS.get_operation(operation)
