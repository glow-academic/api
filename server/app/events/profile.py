"""Profile event declarations for centralized delivery."""

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
from app.infra.profile.types import (
    CreateProfileApiRequest,
    CreateProfileApiResponse,
    DeleteProfileApiRequest,
    DeleteProfileApiResponse,
    DuplicateProfileApiRequest,
    DuplicateProfileApiResponse,
    EmulateProfileApiRequest,
    EmulateProfileApiResponse,
    ExportProfileApiRequest,
    ExportProfileApiResponse,
    GetProfileApiRequest,
    GetProfileApiResponse,
    GetProfileDraftsApiResponse,
    PatchProfileDraftApiRequest,
    PatchProfileDraftApiResponse,
    ProfileContextApiResponse,
    UnemulateProfileApiResponse,
    UpdateProfileApiRequest,
    UpdateProfileApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _profile_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve profile IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("profile_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("profile_id")
        ]
    )


def _profile_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated profile ID from output."""
    del arguments
    return _uuid_list([output.get("profile_id")])


def _profile_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _profile_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


PROFILE_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "context": OperationEventConfig(
        operation="context",
        scope="entity",
        entity_key="profile_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ProfileContextApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.profile.context.viewed": None},
        resolve_entity_ids=lambda arguments, output: _profile_request_entity_ids(
            arguments, output, "profile_id"
        ),
    ),
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="target_profile_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetProfileApiRequest,
            "completed": GetProfileApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.profile.viewed": None},
        resolve_entity_ids=lambda arguments, output: _profile_request_entity_ids(
            arguments, output, "target_profile_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateProfileApiRequest,
            "completed": CreateProfileApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.profile.created": CreateProfileApiResponse},
        resolve_entity_ids=_profile_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        scope="entity",
        entity_key="profile_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateProfileApiRequest,
            "completed": UpdateProfileApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.profile.updated": UpdateProfileApiResponse},
        resolve_entity_ids=_profile_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        scope="entity",
        entity_key="profile_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteProfileApiRequest,
            "completed": DeleteProfileApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.profile.deleted": DeleteProfileApiResponse},
        resolve_entity_ids=_profile_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        scope="entity",
        entity_key="target_profile_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateProfileApiRequest,
            "completed": DuplicateProfileApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.profile.duplicated": DuplicateProfileApiResponse},
        resolve_entity_ids=_profile_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchProfileDraftApiRequest,
            "completed": PatchProfileDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.profile.draft.saved": PatchProfileDraftApiResponse,
        },
        resolve_entity_ids=_profile_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.profile.drafts.viewed": GetProfileDraftsApiResponse,
        },
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.profile.search.performed": None},
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
        domain_events={"artifacts.profile.docs.viewed": None},
        resolve_entity_ids=lambda arguments, output: _profile_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        scope="collection",
        entity_key="profile_export_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportProfileApiRequest,
            "completed": ExportProfileApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.profile.exported": ExportProfileApiResponse},
        resolve_entity_ids=lambda arguments, output: _profile_request_entity_ids(
            arguments, output, "profile_export_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.profile.refreshed": None},
    ),
    "emulate": OperationEventConfig(
        operation="emulate",
        scope="entity",
        entity_key="target_profile_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": EmulateProfileApiRequest,
            "completed": EmulateProfileApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.profile.emulated": EmulateProfileApiResponse},
        resolve_entity_ids=lambda arguments, output: _profile_request_entity_ids(
            arguments, output, "target_profile_id"
        ),
    ),
    "unemulate": OperationEventConfig(
        operation="unemulate",
        scope="entity",
        entity_key="profile_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": UnemulateProfileApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.profile.unemulated": UnemulateProfileApiResponse},
        resolve_entity_ids=lambda arguments, output: _profile_request_entity_ids(
            arguments, output, "profile_id"
        ),
    ),
}

PROFILE_EVENTS = ArtifactEventsConfig(
    artifact="profile",
    operations=PROFILE_EVENT_CONFIGS,
)


def get_profile_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a profile operation."""
    return PROFILE_EVENTS.get_operation(operation)
