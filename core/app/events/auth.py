"""Auth event declarations for centralized delivery."""

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
from app.infra.auth.types import (
    CreateAuthApiRequest,
    CreateAuthApiResponse,
    DeleteAuthApiRequest,
    DeleteAuthApiResponse,
    DuplicateAuthApiRequest,
    DuplicateAuthApiResponse,
    ExportAuthApiRequest,
    ExportAuthApiResponse,
    GetAuthApiRequest,
    GetAuthApiResponse,
    GetAuthDraftsApiResponse,
    PatchAuthDraftApiRequest,
    PatchAuthDraftApiResponse,
    UpdateAuthApiRequest,
    UpdateAuthApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _auth_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve auth IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("auth_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("auth_id")
        ]
    )


def _auth_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated auth ID from output."""
    del arguments
    return _uuid_list([output.get("auth_id")])


def _auth_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _auth_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


AUTH_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="auth_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetAuthApiRequest,
            "completed": GetAuthApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.auth.viewed": None},
        resolve_entity_ids=lambda arguments, output: _auth_request_entity_ids(
            arguments, output, "auth_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateAuthApiRequest,
            "completed": CreateAuthApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.auth.created": CreateAuthApiResponse},
        resolve_entity_ids=_auth_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        scope="entity",
        entity_key="auth_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateAuthApiRequest,
            "completed": UpdateAuthApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.auth.updated": UpdateAuthApiResponse},
        resolve_entity_ids=_auth_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        scope="entity",
        entity_key="auth_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteAuthApiRequest,
            "completed": DeleteAuthApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.auth.deleted": DeleteAuthApiResponse},
        resolve_entity_ids=_auth_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        scope="entity",
        entity_key="auth_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateAuthApiRequest,
            "completed": DuplicateAuthApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.auth.duplicated": DuplicateAuthApiResponse},
        resolve_entity_ids=_auth_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchAuthDraftApiRequest,
            "completed": PatchAuthDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.auth.draft.saved": PatchAuthDraftApiResponse},
        resolve_entity_ids=_auth_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.auth.drafts.viewed": GetAuthDraftsApiResponse},
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.auth.search.performed": None},
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
        domain_events={"artifacts.auth.docs.viewed": None},
        resolve_entity_ids=lambda arguments, output: _auth_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        scope="collection",
        entity_key="auth_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportAuthApiRequest,
            "completed": ExportAuthApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.auth.exported": ExportAuthApiResponse},
        resolve_entity_ids=lambda arguments, output: _auth_request_entity_ids(
            arguments, output, "auth_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.auth.refreshed": None},
    ),
}

AUTH_EVENTS = ArtifactEventsConfig(
    artifact="auth",
    operations=AUTH_EVENT_CONFIGS,
)


def get_auth_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for an auth operation."""
    return AUTH_EVENTS.get_operation(operation)
