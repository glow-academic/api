"""Field page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the field page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Artifact/entry/resource docs — schema introspection (same as docs.py)
  3. Permission evaluation — concrete booleans for THIS caller
  4. Entity permissions — can_edit/can_delete when entity_id is provided
  5. Page metadata — titles and descriptions for list/detail/new views
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Artifact tool docs
from app.tools.artifacts.field.docs import get_field_docs
from app.tools.artifacts.field.get import get_fields as get_field_artifacts

# Entry tool docs
from app.tools.entries.field_drafts.docs import get_field_drafts_docs

# Resource tool docs
from app.tools.resources.conditional_parameters.docs import (
    get_conditional_parameters_docs,
)
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.parameters.docs import get_parameters_docs

from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Fields",
    list_description="Manage form field configurations.",
    detail_title="— Field",
    detail_description="View and edit field configuration and linked resources.",
    new_title="New Field",
    new_description="Create a new field.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a field by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_field_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """field page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("field/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "field", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_field_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_field_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Field page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: artifact docs + entry docs + all resource docs
         + entity permissions context (if entity_id)
         + entity name (if entity_id)
      3. Evaluate caller permissions using profile data
      4. Assemble ComposedContextResponse
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches + entity resolution ----------------------
    # Each branch acquires its own connection from the pool.

    async def _get_field_docs() -> list:
        async with pool.acquire() as conn:
            return await get_field_docs(conn)

    async def _get_field_drafts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_field_drafts_docs(conn)

    async def _get_names_docs() -> list:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_conditional_parameters_docs() -> list:
        async with pool.acquire() as conn:
            return await get_conditional_parameters_docs(conn)

    async def _get_departments_docs() -> list:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_parameters_docs() -> list:
        async with pool.acquire() as conn:
            return await get_parameters_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.field.permissions_context import (
            resolve_field_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_field_permissions_context(conn, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

    (
        artifact,
        drafts,
        names,
        descriptions,
        conditional_parameters,
        departments,
        flags,
        parameters,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_field_docs(),
        _get_field_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_conditional_parameters_docs(),
        _get_departments_docs(),
        _get_flags_docs(),
        _get_parameters_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.field.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        compute_disabled_reason,
        has_access,
    )

    caller_permissions = CallerPermissions(
        can_create=compute_can_create(
            profile.role_level,
            profile.role_permissions,
            profile.department_ids,
        ),
        can_draft=compute_can_draft(
            profile.role_level,
            profile.role_permissions,
        ),
        can_duplicate=compute_can_duplicate(
            profile.role_level,
            profile.role_permissions,
        ),
    )

    # Entity-level permissions (only when entity_id was provided and found)
    if entity_id and entity_perms and entity_perms.exists:
        caller_permissions.has_access = has_access(
            profile.role_level,
            profile.department_ids,
            entity_perms.department_ids,
        )
        caller_permissions.can_edit = compute_can_edit(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_parameter_count,
            profile.department_ids,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_parameter_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_parameter_count,
            profile.department_ids,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Create a field", content="Create a new custom field with appropriate type, validation, and defaults."),
            StarterPrompt(title="From requirements", content="I need a specific data field — help me configure it with proper validation."),
            StarterPrompt(title="Template-based", content="Create a field from a common pattern like text input, dropdown, or date picker."),
        ],
        "search": [
            StarterPrompt(title="Find fields", content="Help me find fields that match specific types or validation criteria."),
            StarterPrompt(title="Compare fields", content="Compare my fields and identify redundant or overlapping definitions."),
            StarterPrompt(title="Audit fields", content="Review all fields and flag any with missing validation or incomplete configs."),
        ],
        "update": [
            StarterPrompt(title="Enhance field", content="Improve this field's validation rules, description, and default values."),
            StarterPrompt(title="Add constraints", content="Add validation constraints, help text, and conditional logic to this field."),
            StarterPrompt(title="Refine type", content="Optimize this field's data type and format for its intended use case."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & modify", content="Duplicate this field and modify the type or validation for a different use case."),
            StarterPrompt(title="Bulk clone", content="Create variations of this field for different parameter configurations."),
        ],
        "draft": [
            StarterPrompt(title="Draft field", content="Start drafting a new field — suggest a name, type, and validation rules."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements before saving."),
        ],
        "export": [
            StarterPrompt(title="Export schema", content="Generate a summary of all fields and their validation configurations."),
            StarterPrompt(title="Export field map", content="Create a report mapping fields to their usage across artifacts."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.field.create import create_field
    from app.routes.field.delete import delete_field
    from app.routes.field.draft import patch_field_draft
    from app.routes.field.duplicate import duplicate_field
    from app.routes.field.export import export_fields
    from app.routes.field.get import get_field
    from app.routes.field.search import search_field
    from app.routes.field.update import update_field

    return ComposedContextResponse(
        name="field",
        type="artifact",
        description=(
            "Fields define form field configurations. "
            "Each field links to resources (names, descriptions, departments, "
            "flags, parameters, conditional_parameters) "
            "via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            conditional_parameters,
            departments,
            flags,
            parameters,
        ],
        permission_docs=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the field.",
            ),
            get_operation_info(
                compute_can_edit,
                description="Unified edit permission for UI and save enforcement.",
            ),
            get_operation_info(
                compute_can_delete,
                description="Delete permission — same as edit + usage check.",
            ),
            get_operation_info(
                compute_can_duplicate,
                description="Duplicate — role-only check.",
            ),
            get_operation_info(
                compute_can_create,
                description="Create new artifact — role + department check.",
            ),
            get_operation_info(
                compute_can_draft,
                description="Draft — role-only check.",
            ),
        ],
        api_operations=[
            get_operation_info(
                get_field,
                description="POST /get — Get a single field by ID with hydrated resources.",
            ),
            get_operation_info(
                search_field,
                description="POST /search — Paginated field search with filters.",
            ),
            get_operation_info(
                create_field,
                description="POST /create — Create a new field artifact.",
            ),
            get_operation_info(
                update_field,
                description="POST /update — Update an existing field's resource links.",
            ),
            get_operation_info(
                duplicate_field,
                description="POST /duplicate — Duplicate an existing field.",
            ),
            get_operation_info(
                delete_field,
                description="POST /delete — Delete a field.",
            ),
            get_operation_info(
                patch_field_draft,
                description="PATCH /draft — Create or patch a field draft (autosave).",
            ),
            get_operation_info(
                export_fields,
                description="POST /export — Export fields as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
