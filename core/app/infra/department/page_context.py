"""Department page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the department page:
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

from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Artifact tool docs
from app.tools.artifacts.department.docs import get_department_docs
from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)

# Entry tool docs
from app.tools.entries.department_drafts.docs import (
    get_department_drafts_docs,
)

# Resource tool docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.settings.docs import get_settings_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Departments",
    list_description="Manage organizational units.",
    detail_title="— Department",
    detail_description="View and edit department configuration and linked resources.",
    new_title="New Department",
    new_description="Create a new department.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a department by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_department_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """department page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("department/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "department", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_department_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_department_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Department page context.

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

    async def _get_department_docs() -> list:
        async with pool.acquire() as conn:
            return await get_department_docs(conn)

    async def _get_department_drafts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_department_drafts_docs(conn)

    async def _get_names_docs() -> list:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_settings_docs() -> list:
        async with pool.acquire() as conn:
            return await get_settings_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.department.permissions_context import (
            resolve_department_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_department_permissions_context(conn, entity_id)

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
        settings,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_department_docs(),
        _get_department_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_flags_docs(),
        _get_settings_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.department.permissions import (
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
            profile.role_permissions,
        )
        caller_permissions.can_edit = compute_can_edit(
            profile.role_level,
            profile.role_permissions,
            entity_perms.usage_count,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.usage_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.usage_count,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Create a department", content="Create a new organizational department with clear responsibilities and structure."),
            StarterPrompt(title="From description", content="I have a team structure in mind — help me formalize it as a department."),
            StarterPrompt(title="Template-based", content="Create a department from a common template like Engineering, Sales, or Support."),
        ],
        "search": [
            StarterPrompt(title="Find departments", content="Help me find departments that match specific organizational criteria."),
            StarterPrompt(title="Review structure", content="Review my departments and suggest improvements to the organizational hierarchy."),
            StarterPrompt(title="Audit departments", content="Check all departments for missing descriptions or overlapping responsibilities."),
        ],
        "update": [
            StarterPrompt(title="Enhance department", content="Improve this department's description and organizational details."),
            StarterPrompt(title="Refine scope", content="Clarify this department's boundaries and responsibilities within the organization."),
            StarterPrompt(title="Add settings", content="Add missing settings and configuration details to this department."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & rename", content="Duplicate this department to create a parallel unit with a different focus."),
            StarterPrompt(title="Bulk clone", content="Create variations of this department for multiple regions or divisions."),
        ],
        "draft": [
            StarterPrompt(title="Draft department", content="Start drafting a new department — suggest a name, scope, and responsibilities."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements before saving."),
        ],
        "export": [
            StarterPrompt(title="Export overview", content="Generate a summary of all departments and their organizational roles."),
            StarterPrompt(title="Export hierarchy", content="Create a report showing department structure and interdependencies."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.department.create import create_department
    from app.routes.department.delete import delete_department
    from app.routes.department.draft import patch_department_draft
    from app.routes.department.duplicate import duplicate_department
    from app.routes.department.export import export_departments
    from app.routes.department.get import get_department
    from app.routes.department.search import search_department
    from app.routes.department.update import update_department

    return ComposedContextResponse(
        name="department",
        type="artifact",
        description=(
            "Departments define organizational units. "
            "Each department links to resources (names, descriptions, "
            "flags, settings) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            flags,
            settings,
        ],
        permission_docs=[
            get_operation_info(
                has_access,
                description="View access — role-based check for department visibility.",
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
                description="Create new artifact — role + permission check.",
            ),
            get_operation_info(
                compute_can_draft,
                description="Draft — role-only check.",
            ),
        ],
        api_operations=[
            get_operation_info(
                get_department,
                description="POST /get — Get a single department by ID with hydrated resources.",
            ),
            get_operation_info(
                search_department,
                description="POST /search — Paginated department search with filters.",
            ),
            get_operation_info(
                create_department,
                description="POST /create — Create a new department artifact.",
            ),
            get_operation_info(
                update_department,
                description="POST /update — Update an existing department's resource links.",
            ),
            get_operation_info(
                duplicate_department,
                description="POST /duplicate — Duplicate an existing department.",
            ),
            get_operation_info(
                delete_department,
                description="POST /delete — Delete a department.",
            ),
            get_operation_info(
                patch_department_draft,
                description="PATCH /draft — Create or patch a department draft (autosave).",
            ),
            get_operation_info(
                export_departments,
                description="POST /export — Export departments as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
