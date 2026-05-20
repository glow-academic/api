"""Profile page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the profile page:
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
from app.tools.artifacts.profile.docs import get_profile_docs
from app.tools.artifacts.profile.get import (
    get_profiles as get_profile_artifacts,
)

# Entry tool docs
from app.tools.entries.profile_drafts.docs import get_profile_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.emails.docs import get_emails_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.request_limits.docs import get_request_limits_docs
from app.tools.resources.roles.docs import get_roles_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Profiles",
    list_description="Manage user accounts and permissions.",
    detail_title="— Profile",
    detail_description="View and edit profile configuration and linked resources.",
    new_title="New Profile",
    new_description="Create a new user profile.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a profile by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_profile_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """profile page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("profile/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "profile", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_profile_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_profile_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Profile page context.

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

    async def _get_profile_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_profile_docs(conn)

    async def _get_profile_drafts_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_profile_drafts_docs(conn)

    async def _get_names_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_emails_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_emails_docs(conn)

    async def _get_flags_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_request_limits_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_request_limits_docs(conn)

    async def _get_roles_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_roles_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.profile.permissions_context import (
            resolve_profile_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_profile_permissions_context(conn, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

    (
        artifact,
        drafts,
        names,
        emails,
        flags,
        departments,
        request_limits,
        roles,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_profile_docs(),
        _get_profile_drafts_docs(),
        _get_names_docs(),
        _get_emails_docs(),
        _get_flags_docs(),
        _get_departments_docs(),
        _get_request_limits_docs(),
        _get_roles_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.profile.permissions import (
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
            entity_id == profile_id,  # target_is_self
            entity_perms.department_ids,
            user_department_ids=profile.department_ids,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_id == profile_id,  # target_is_self
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_id == profile_id,  # target_is_self
            entity_perms.department_ids,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Create a profile", content="Create a new user profile with appropriate role and department assignments."),
            StarterPrompt(title="From role", content="I need a profile for a specific role — help me configure the right permissions."),
            StarterPrompt(title="Template-based", content="Create a profile from a common role template like admin, instructor, or student."),
        ],
        "search": [
            StarterPrompt(title="Find profiles", content="Help me find profiles by role, department, or permission level."),
            StarterPrompt(title="Compare profiles", content="Compare my profiles and identify inconsistent role or department assignments."),
            StarterPrompt(title="Audit access", content="Review all profiles and flag any with excessive or missing permissions."),
        ],
        "update": [
            StarterPrompt(title="Update permissions", content="Adjust this profile's permissions and access levels for their role."),
            StarterPrompt(title="Reassign departments", content="Update this profile's department assignments to match their current responsibilities."),
            StarterPrompt(title="Review access", content="Audit this profile's access rights and suggest appropriate changes."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone profile", content="Duplicate this profile to create another user with the same role and permissions."),
            StarterPrompt(title="Team onboarding", content="Clone this profile multiple times for new team members joining the same department."),
        ],
        "draft": [
            StarterPrompt(title="Draft profile", content="Start drafting a new profile — suggest a role and department configuration."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements to permissions before saving."),
        ],
        "export": [
            StarterPrompt(title="Export roster", content="Generate a summary of all profiles with their roles and department assignments."),
            StarterPrompt(title="Export audit", content="Create a permissions audit report showing access levels across all profiles."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.profile.create import create_profile
    from app.routes.profile.delete import delete_profile
    from app.routes.profile.draft import patch_profile_draft
    from app.routes.profile.duplicate import duplicate_profile
    from app.routes.profile.export import export_profiles
    from app.routes.profile.get import get_profile
    from app.routes.profile.search import search_profile
    from app.routes.profile.update import update_profile

    return ComposedContextResponse(
        name="profile",
        type="artifact",
        description=(
            "Profiles define user accounts and permissions. "
            "Each profile links to resources (names, departments, emails, "
            "flags, request_limits, roles) via junction tables."
        ),
        artifact=(artifact if schema else None),
        entries=([drafts] if schema else None),
        resources=([
            names,
            emails,
            flags,
            departments,
            request_limits,
            roles,
        ] if schema else None),
        permission_docs=([
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the profile.",
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
        ] if schema else None),
        api_operations=([
            get_operation_info(
                get_profile,
                description="POST /get — Get a single profile by ID with hydrated resources.",
            ),
            get_operation_info(
                search_profile,
                description="POST /search — Paginated profile search with filters.",
            ),
            get_operation_info(
                create_profile,
                description="POST /create — Create a new profile artifact.",
            ),
            get_operation_info(
                update_profile,
                description="POST /update — Update an existing profile's resource links.",
            ),
            get_operation_info(
                duplicate_profile,
                description="POST /duplicate — Duplicate an existing profile.",
            ),
            get_operation_info(
                delete_profile,
                description="POST /delete — Delete a profile.",
            ),
            get_operation_info(
                patch_profile_draft,
                description="PATCH /draft — Create or patch a profile draft (autosave).",
            ),
            get_operation_info(
                export_profiles,
                description="POST /export — Export profiles as denormalized CSV.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
