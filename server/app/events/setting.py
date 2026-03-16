"""Setting event declarations for centralized delivery."""

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
from app.infra.setting.types import (
    CreateSettingApiRequest,
    CreateSettingApiResponse,
    DeleteSettingApiRequest,
    DeleteSettingApiResponse,
    DuplicateSettingApiRequest,
    DuplicateSettingApiResponse,
    ExportSettingApiRequest,
    ExportSettingApiResponse,
    GetSettingApiRequest,
    GetSettingApiResponse,
    GetSettingDraftsApiResponse,
    PatchSettingDraftApiRequest,
    PatchSettingDraftApiResponse,
    UpdateSettingApiRequest,
    UpdateSettingApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _setting_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve setting IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("setting_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("setting_id")
        ]
    )


def _setting_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated setting ID from output."""
    del arguments
    return _uuid_list([output.get("setting_id")])


def _setting_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _setting_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


SETTING_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        domain_events={"artifacts.setting.viewed": None},
        scope="entity",
        entity_key="setting_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetSettingApiRequest,
            "completed": GetSettingApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _setting_request_entity_ids(
            arguments, output, "setting_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        domain_events={"artifacts.setting.created": CreateSettingApiResponse},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateSettingApiRequest,
            "completed": CreateSettingApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_setting_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        domain_events={"artifacts.setting.updated": UpdateSettingApiResponse},
        scope="entity",
        entity_key="setting_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateSettingApiRequest,
            "completed": UpdateSettingApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_setting_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        domain_events={"artifacts.setting.deleted": DeleteSettingApiResponse},
        scope="entity",
        entity_key="setting_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteSettingApiRequest,
            "completed": DeleteSettingApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_setting_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        domain_events={"artifacts.setting.duplicated": DuplicateSettingApiResponse},
        scope="entity",
        entity_key="setting_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateSettingApiRequest,
            "completed": DuplicateSettingApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_setting_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        domain_events={
            "artifacts.setting.draft.saved": PatchSettingDraftApiResponse,
        },
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchSettingDraftApiRequest,
            "completed": PatchSettingDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=_setting_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        domain_events={
            "artifacts.setting.drafts.viewed": GetSettingDraftsApiResponse,
        },
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        domain_events={"artifacts.setting.search.performed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        include_call_lifecycle=False,
    ),
    "docs": OperationEventConfig(
        operation="docs",
        domain_events={"artifacts.setting.docs.viewed": None},
        scope="entity",
        entity_key="entity_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ComposedDocsResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _setting_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        domain_events={"artifacts.setting.exported": ExportSettingApiResponse},
        scope="collection",
        entity_key="setting_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportSettingApiRequest,
            "completed": ExportSettingApiResponse,
            "failed": OperationErrorEvent,
        },
        resolve_entity_ids=lambda arguments, output: _setting_request_entity_ids(
            arguments, output, "setting_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.setting.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

SETTING_EVENTS = ArtifactEventsConfig(
    artifact="setting",
    operations=SETTING_EVENT_CONFIGS,
)


def get_setting_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a setting operation."""
    return SETTING_EVENTS.get_operation(operation)
