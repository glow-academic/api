"""Persona event declarations for centralized delivery."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.events.generation import PersonaGenerationProgressEvent
from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    default_filter_events,
    require_authenticated_profile,
)
from app.infra.docs.types import ComposedDocsResponse
from app.infra.persona.permissions import (
    compute_can_create,
    compute_can_delete,
    compute_can_draft,
    compute_can_duplicate,
    compute_can_edit,
    has_access,
)
from app.infra.persona.permissions_context import resolve_persona_permissions_context
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.persona.types import (
    CreatePersonaApiRequest,
    CreatePersonaApiResponse,
    DeletePersonaApiRequest,
    DeletePersonaApiResponse,
    DuplicatePersonaApiRequest,
    DuplicatePersonaApiResponse,
    ExportPersonaApiRequest,
    ExportPersonaApiResponse,
    GetPersonaApiRequest,
    GetPersonaApiResponse,
    GetPersonaDraftsApiResponse,
    PatchPersonaDraftApiRequest,
    PatchPersonaDraftApiResponse,
    UpdatePersonaApiRequest,
    UpdatePersonaApiResponse,
)

EventRecord = dict[str, Any]


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _persona_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve persona IDs from bulk create/update/delete style outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("persona_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("persona_id")
        ]
    )


def _persona_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated persona ID from the operation output."""
    del arguments
    return _uuid_list([output.get("persona_id")])


def _persona_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments first, then output."""
    del output
    return _uuid_list([arguments.get(key)])


def _persona_export_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve exported persona target when export is entity-scoped."""
    return _persona_request_entity_ids(arguments, output, "persona_id")


def _persona_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


async def _resolve_profile(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
) -> Any | None:
    """Resolve actor identity for event authorization."""
    return await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
        draft_id=draft_id,
    )


async def _can_subscribe_persona_read(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    session_id: UUID | None = None,
    event_types: list[str] | None = None,
) -> bool:
    """Read-level visibility for persona entity or collection events."""
    del event_types
    profile = await _resolve_profile(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
    )
    if profile is None:
        return False

    if entity_id is None:
        return True

    perms = await resolve_persona_permissions_context(pool, entity_id)
    if not perms.exists:
        return False

    return has_access(
        profile.role,
        profile.department_ids,
        perms.department_ids,
    )


async def _can_subscribe_persona_create(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    session_id: UUID | None = None,
    event_types: list[str] | None = None,
) -> bool:
    """Create-level visibility for persona collection events."""
    del entity_id, event_types
    profile = await _resolve_profile(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
    )
    if profile is None:
        return False

    # Collection-scoped create events do not carry department scope yet.
    return compute_can_create(profile.role, ["department-scoped"])


async def _can_subscribe_persona_edit(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    session_id: UUID | None = None,
    event_types: list[str] | None = None,
) -> bool:
    """Edit-level visibility for persona entity events."""
    del event_types
    if entity_id is None:
        return False

    profile = await _resolve_profile(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
    )
    if profile is None:
        return False

    perms = await resolve_persona_permissions_context(pool, entity_id)
    if not perms.exists:
        return False

    return compute_can_edit(
        user_role=profile.role,
        persona_department_ids=perms.department_ids,
        active_scenario_count=perms.active_scenario_count,
        user_department_ids=profile.department_ids,
    )


async def _can_subscribe_persona_delete(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    session_id: UUID | None = None,
    event_types: list[str] | None = None,
) -> bool:
    """Delete-level visibility for persona entity events."""
    del event_types
    if entity_id is None:
        return False

    profile = await _resolve_profile(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
    )
    if profile is None:
        return False

    perms = await resolve_persona_permissions_context(pool, entity_id)
    if not perms.exists:
        return False

    return compute_can_delete(
        user_role=profile.role,
        persona_department_ids=perms.department_ids,
        active_scenario_count=perms.active_scenario_count,
    )


async def _can_subscribe_persona_duplicate(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    session_id: UUID | None = None,
    event_types: list[str] | None = None,
) -> bool:
    """Duplicate-level visibility for persona entity events."""
    del entity_id, event_types
    profile = await _resolve_profile(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
    )
    if profile is None:
        return False

    return compute_can_duplicate(profile.role)


async def _can_subscribe_persona_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    session_id: UUID | None = None,
    event_types: list[str] | None = None,
) -> bool:
    """Draft-level visibility for persona draft entity/collection events."""
    del entity_id, event_types
    profile = await _resolve_profile(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
    )
    if profile is None:
        return False

    return compute_can_draft(profile.role)


async def _passthrough_filter(
    profile_id: UUID,
    events: list[EventRecord],
) -> list[EventRecord]:
    """Default event filter placeholder."""
    return await default_filter_events(profile_id, events)


PERSONA_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="persona_id",
        can_subscribe=_can_subscribe_persona_read,
        lifecycle_models={
            "started": GetPersonaApiRequest,
            "completed": GetPersonaApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.persona.viewed": None,
        },
        filter_events=_passthrough_filter,
    ),
    "create": OperationEventConfig(
        operation="create",
        scope="collection",
        entity_key=None,
        can_subscribe=_can_subscribe_persona_create,
        lifecycle_models={
            "started": CreatePersonaApiRequest,
            "completed": CreatePersonaApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.persona.created": CreatePersonaApiResponse,
        },
        resolve_entity_ids=_persona_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        scope="entity",
        entity_key="persona_id",
        can_subscribe=_can_subscribe_persona_edit,
        lifecycle_models={
            "started": UpdatePersonaApiRequest,
            "completed": UpdatePersonaApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.persona.updated": UpdatePersonaApiResponse,
        },
        resolve_entity_ids=_persona_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        scope="entity",
        entity_key="persona_id",
        can_subscribe=_can_subscribe_persona_delete,
        lifecycle_models={
            "started": DeletePersonaApiRequest,
            "completed": DeletePersonaApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.persona.deleted": DeletePersonaApiResponse,
        },
        resolve_entity_ids=_persona_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        scope="entity",
        entity_key="persona_id",
        can_subscribe=_can_subscribe_persona_duplicate,
        lifecycle_models={
            "started": DuplicatePersonaApiRequest,
            "completed": DuplicatePersonaApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.persona.duplicated": DuplicatePersonaApiResponse,
        },
        resolve_entity_ids=_persona_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        scope="entity",
        entity_key="draft_id",
        can_subscribe=_can_subscribe_persona_draft,
        lifecycle_models={
            "started": PatchPersonaDraftApiRequest,
            "completed": PatchPersonaDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.persona.draft.saved": PatchPersonaDraftApiResponse,
            "artifacts.persona.draft.progress": PersonaGenerationProgressEvent,
            "artifacts.persona.draft.complete": None,
            "artifacts.persona.draft.error": OperationErrorEvent,
        },
        resolve_entity_ids=_persona_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        scope="collection",
        entity_key=None,
        can_subscribe=_can_subscribe_persona_draft,
        domain_events={
            "artifacts.persona.drafts.viewed": GetPersonaDraftsApiResponse,
        },
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        scope="collection",
        entity_key=None,
        can_subscribe=_can_subscribe_persona_read,
        domain_events={
            "artifacts.persona.search.performed": None,
        },
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
        domain_events={
            "artifacts.persona.docs.viewed": None,
        },
        resolve_entity_ids=lambda arguments, output: _persona_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        scope="collection",
        entity_key="persona_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportPersonaApiRequest,
            "completed": ExportPersonaApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.persona.exported": ExportPersonaApiResponse,
        },
        resolve_entity_ids=_persona_export_entity_ids,
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.persona.refreshed": None,
        },
    ),
}

PERSONA_EVENTS = ArtifactEventsConfig(
    artifact="persona",
    operations=PERSONA_EVENT_CONFIGS,
)

PERSONA_EVENT_TYPES: tuple[str, ...] = PERSONA_EVENTS.event_types


def get_persona_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a persona operation."""
    return PERSONA_EVENTS.get_operation(operation)
