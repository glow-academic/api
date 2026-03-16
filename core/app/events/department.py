"""Department event declarations for centralized delivery."""

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
from app.infra.department.types import (
    CreateDepartmentApiRequest,
    CreateDepartmentApiResponse,
    DeleteDepartmentApiRequest,
    DeleteDepartmentApiResponse,
    DuplicateDepartmentApiRequest,
    DuplicateDepartmentApiResponse,
    ExportDepartmentApiRequest,
    ExportDepartmentApiResponse,
    GetDepartmentApiRequest,
    GetDepartmentApiResponse,
    GetDepartmentDraftsApiResponse,
    PatchDepartmentDraftApiRequest,
    PatchDepartmentDraftApiResponse,
    UpdateDepartmentApiRequest,
    UpdateDepartmentApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _department_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve department IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("department_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("department_id")
        ]
    )


def _department_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated department ID from output."""
    del arguments
    return _uuid_list([output.get("department_id")])


def _department_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _department_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


DEPARTMENT_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        domain_events={"artifacts.department.viewed": None},
        scope="entity",
        entity_key="department_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetDepartmentApiRequest,
            "completed": GetDepartmentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _department_request_entity_ids(
            arguments, output, "department_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        domain_events={"artifacts.department.created": CreateDepartmentApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateDepartmentApiRequest,
            "completed": CreateDepartmentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_department_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        domain_events={"artifacts.department.updated": UpdateDepartmentApiResponse},
        scope="entity",
        entity_key="department_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateDepartmentApiRequest,
            "completed": UpdateDepartmentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_department_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        domain_events={"artifacts.department.deleted": DeleteDepartmentApiResponse},
        scope="entity",
        entity_key="department_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteDepartmentApiRequest,
            "completed": DeleteDepartmentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_department_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        domain_events={
            "artifacts.department.duplicated": DuplicateDepartmentApiResponse,
        },
        scope="entity",
        entity_key="department_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateDepartmentApiRequest,
            "completed": DuplicateDepartmentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_department_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        domain_events={
            "artifacts.department.draft.saved": PatchDepartmentDraftApiResponse,
        },
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchDepartmentDraftApiRequest,
            "completed": PatchDepartmentDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_department_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        domain_events={
            "artifacts.department.drafts.viewed": GetDepartmentDraftsApiResponse,
        },
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        domain_events={"artifacts.department.search.performed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "docs": OperationEventConfig(
        operation="docs",
        domain_events={"artifacts.department.docs.viewed": None},
        scope="entity",
        entity_key="entity_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ComposedDocsResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _department_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        domain_events={"artifacts.department.exported": ExportDepartmentApiResponse},
        scope="collection",
        entity_key="department_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportDepartmentApiRequest,
            "completed": ExportDepartmentApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _department_request_entity_ids(
            arguments, output, "department_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.department.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

DEPARTMENT_EVENTS = ArtifactEventsConfig(
    artifact="department",
    operations=DEPARTMENT_EVENT_CONFIGS,
)


def get_department_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a department operation."""
    return DEPARTMENT_EVENTS.get_operation(operation)
