"""Parameter page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the parameter page:
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
from app.tools.artifacts.parameter.docs import get_parameter_docs
from app.tools.artifacts.parameter.get import (
    get_parameters as get_parameter_artifacts,
)

# Entry tool docs
from app.tools.entries.parameter_drafts.docs import get_parameter_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.parameter_fields.docs import (
    get_parameter_fields_docs,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Parameters",
    list_description="Manage configurable parameter sets.",
    detail_title="— Parameter",
    detail_description="View and edit parameter configuration and linked resources.",
    new_title="New Parameter",
    new_description="Create a new parameter configuration.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a parameter by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_parameter_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def page_context_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Parameter page context.

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

    async def _get_parameter_docs() -> list:
        async with pool.acquire() as conn:
            return await get_parameter_docs(conn)

    async def _get_parameter_drafts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_parameter_drafts_docs(conn)

    async def _get_names_docs() -> list:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> list:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_parameter_fields_docs() -> list:
        async with pool.acquire() as conn:
            return await get_parameter_fields_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.parameter.permissions_context import (
            resolve_parameter_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_parameter_permissions_context(conn, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

    (
        artifact,
        drafts,
        names,
        descriptions,
        flags,
        departments,
        parameter_fields,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_parameter_docs(),
        _get_parameter_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_flags_docs(),
        _get_departments_docs(),
        _get_parameter_fields_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.parameter.permissions import (
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
            entity_perms.active_scenario_count,
            profile.department_ids,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_scenario_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_scenario_count,
            profile.department_ids,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Define a parameter", content="Create a new configuration parameter with appropriate type, constraints, and default value."),
            StarterPrompt(title="From requirements", content="I need a specific parameter — help me define it with proper validation and type."),
            StarterPrompt(title="Template-based", content="Create a parameter from a common pattern like toggle, slider, or text input."),
        ],
        "search": [
            StarterPrompt(title="Find parameters", content="Help me find parameters that match specific types or constraint criteria."),
            StarterPrompt(title="Compare parameters", content="Compare my parameters and identify inconsistent defaults or missing constraints."),
            StarterPrompt(title="Audit parameters", content="Review all parameters and flag any with missing validation or unclear descriptions."),
        ],
        "update": [
            StarterPrompt(title="Refine constraints", content="Improve this parameter's validation rules, acceptable ranges, and error messages."),
            StarterPrompt(title="Update defaults", content="Optimize this parameter's default value based on common usage patterns."),
            StarterPrompt(title="Add description", content="Add a clear description and usage guidance to this parameter."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & adjust", content="Duplicate this parameter and modify its constraints for a different use case."),
            StarterPrompt(title="Bulk clone", content="Create several variations of this parameter with different default values."),
        ],
        "draft": [
            StarterPrompt(title="Draft parameter", content="Start drafting a new parameter — suggest a name, type, and default value."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements to constraints before saving."),
        ],
        "export": [
            StarterPrompt(title="Export summary", content="Generate a summary of all parameters suitable for documentation or review."),
            StarterPrompt(title="Export analysis", content="Analyze my parameters and create a report on type coverage and defaults."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.parameter.create import create_parameter
    from app.routes.parameter.delete import delete_parameter
    from app.routes.parameter.draft import patch_parameter_draft
    from app.routes.parameter.duplicate import duplicate_parameter
    from app.routes.parameter.export import export_parameters
    from app.routes.parameter.get import get_parameter
    from app.routes.parameter.search import search_parameter
    from app.routes.parameter.update import update_parameter

    return ComposedContextResponse(
        name="parameter",
        type="artifact",
        description=(
            "Parameters define configurable parameter sets. "
            "Each parameter links to resources (names, descriptions, departments, "
            "flags, parameter_fields) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            flags,
            departments,
            parameter_fields,
        ],
        permission_docs=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the parameter.",
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
                get_parameter,
                description="POST /get — Get a single parameter by ID with hydrated resources.",
            ),
            get_operation_info(
                search_parameter,
                description="POST /search — Paginated parameter search with filters.",
            ),
            get_operation_info(
                create_parameter,
                description="POST /create — Create a new parameter artifact.",
            ),
            get_operation_info(
                update_parameter,
                description="POST /update — Update an existing parameter's resource links.",
            ),
            get_operation_info(
                duplicate_parameter,
                description="POST /duplicate — Duplicate an existing parameter.",
            ),
            get_operation_info(
                delete_parameter,
                description="POST /delete — Delete a parameter.",
            ),
            get_operation_info(
                patch_parameter_draft,
                description="PATCH /draft — Create or patch a parameter draft (autosave).",
            ),
            get_operation_info(
                export_parameters,
                description="POST /export — Export parameters as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
