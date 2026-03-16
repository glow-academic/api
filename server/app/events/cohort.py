"""Cohort event declarations for centralized delivery."""

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
from app.infra.cohort.types import (
    CreateCohortApiRequest,
    CreateCohortApiResponse,
    DeleteCohortApiRequest,
    DeleteCohortApiResponse,
    DuplicateCohortApiRequest,
    DuplicateCohortApiResponse,
    ExportCohortApiRequest,
    ExportCohortApiResponse,
    GetCohortApiRequest,
    GetCohortApiResponse,
    GetCohortDraftsApiResponse,
    PatchCohortDraftApiRequest,
    PatchCohortDraftApiResponse,
    UpdateCohortApiRequest,
    UpdateCohortApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _cohort_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve cohort IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("cohort_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("cohort_id")
        ]
    )


def _cohort_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated cohort ID from output."""
    del arguments
    return _uuid_list([output.get("cohort_id")])


def _cohort_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _cohort_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


COHORT_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="cohort_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetCohortApiRequest,
            "completed": GetCohortApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.cohort.viewed": None},
        resolve_entity_ids=lambda arguments, output: _cohort_request_entity_ids(
            arguments, output, "cohort_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateCohortApiRequest,
            "completed": CreateCohortApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.cohort.created": CreateCohortApiResponse},
        resolve_entity_ids=_cohort_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        scope="entity",
        entity_key="cohort_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateCohortApiRequest,
            "completed": UpdateCohortApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.cohort.updated": UpdateCohortApiResponse},
        resolve_entity_ids=_cohort_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        scope="entity",
        entity_key="cohort_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteCohortApiRequest,
            "completed": DeleteCohortApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.cohort.deleted": DeleteCohortApiResponse},
        resolve_entity_ids=_cohort_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        scope="entity",
        entity_key="cohort_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateCohortApiRequest,
            "completed": DuplicateCohortApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.cohort.duplicated": DuplicateCohortApiResponse},
        resolve_entity_ids=_cohort_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchCohortDraftApiRequest,
            "completed": PatchCohortDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.cohort.draft.saved": PatchCohortDraftApiResponse,
        },
        resolve_entity_ids=_cohort_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.cohort.drafts.viewed": GetCohortDraftsApiResponse,
        },
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.cohort.search.performed": None},
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
        domain_events={"artifacts.cohort.docs.viewed": None},
        resolve_entity_ids=lambda arguments, output: _cohort_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        scope="collection",
        entity_key="cohort_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportCohortApiRequest,
            "completed": ExportCohortApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.cohort.exported": ExportCohortApiResponse},
        resolve_entity_ids=lambda arguments, output: _cohort_request_entity_ids(
            arguments, output, "cohort_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.cohort.refreshed": None},
    ),
}

COHORT_EVENTS = ArtifactEventsConfig(
    artifact="cohort",
    operations=COHORT_EVENT_CONFIGS,
)


def get_cohort_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a cohort operation."""
    return COHORT_EVENTS.get_operation(operation)
