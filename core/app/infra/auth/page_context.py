"""Auth page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the auth page:
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
from app.tools.artifacts.auth.docs import get_auth_docs
from app.tools.artifacts.auth.get import get_auths as get_auth_artifacts

# Entry tool docs
from app.tools.entries.auth_drafts.docs import get_auth_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.items.docs import get_items_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.protocols.docs import get_protocols_docs
from app.tools.resources.slugs.docs import get_slugs_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Auth Providers",
    list_description="Manage authentication provider configurations.",
    detail_title="— Auth Provider",
    detail_description="View and edit auth provider configuration and linked resources.",
    new_title="New Auth Provider",
    new_description="Create a new auth provider.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for an auth by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_auth_artifacts(conn, [entity_id], names=True)
    if not artifacts or not artifacts[0].name_ids:
        return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """auth page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("auth/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "auth", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_auth_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_auth_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Auth page context.

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

    async def _fetch_auth_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as c:
            return await get_auth_docs(c)

    async def _fetch_auth_drafts_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as c:
            return await get_auth_drafts_docs(c)

    async def _fetch_names_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as c:
            return await get_names_docs(c)

    async def _fetch_descriptions_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as c:
            return await get_descriptions_docs(c)

    async def _fetch_departments_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as c:
            return await get_departments_docs(c)

    async def _fetch_flags_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as c:
            return await get_flags_docs(c)

    async def _fetch_items_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as c:
            return await get_items_docs(c)

    async def _fetch_protocols_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as c:
            return await get_protocols_docs(c)

    async def _fetch_slugs_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as c:
            return await get_slugs_docs(c)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.auth.permissions_context import (
            resolve_auth_permissions_context,
        )
        async with pool.acquire() as c:
            return await resolve_auth_permissions_context(c, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

    (
        artifact,
        drafts,
        names,
        descriptions,
        departments,
        flags,
        items,
        protocols,
        slugs,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _fetch_auth_docs(),
        _fetch_auth_drafts_docs(),
        _fetch_names_docs(),
        _fetch_descriptions_docs(),
        _fetch_departments_docs(),
        _fetch_flags_docs(),
        _fetch_items_docs(),
        _fetch_protocols_docs(),
        _fetch_slugs_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.auth.permissions import (
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
        )
        caller_permissions.can_edit = compute_can_edit(
            profile.role_level,
            profile.role_permissions,
            entity_perms.active_settings_count,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.active_settings_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_permissions,
            entity_perms.active_settings_count,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Create auth config", content="Create a new authentication configuration with appropriate security settings."),
            StarterPrompt(title="From requirements", content="I have specific security requirements — help me build an auth configuration."),
            StarterPrompt(title="Role-based config", content="Create an authentication configuration for a specific user role or access level."),
        ],
        "search": [
            StarterPrompt(title="Find auth configs", content="Help me find authentication configurations that match specific security criteria."),
            StarterPrompt(title="Audit security", content="Review all auth configurations and flag potential security vulnerabilities."),
            StarterPrompt(title="Compare configs", content="Compare my auth configurations and identify inconsistencies across providers."),
        ],
        "update": [
            StarterPrompt(title="Enhance config", content="Improve this authentication configuration's security and usability settings."),
            StarterPrompt(title="Add restrictions", content="Add IP restrictions, session limits, or other security constraints to this config."),
            StarterPrompt(title="Tighten security", content="Review this auth config and recommend stricter security settings."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & customize", content="Duplicate this auth config and adjust it for a different user group or environment."),
            StarterPrompt(title="Bulk clone", content="Create variations of this auth config for different access tiers."),
        ],
        "draft": [
            StarterPrompt(title="Draft auth config", content="Start drafting a new auth configuration — suggest protocols and security settings."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest security improvements before saving."),
        ],
        "export": [
            StarterPrompt(title="Export overview", content="Generate a summary of all auth configurations for a security review."),
            StarterPrompt(title="Export audit report", content="Create a security audit report of all authentication configurations."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.auth.create import create_auth
    from app.routes.auth.delete import delete_auth
    from app.routes.auth.draft import patch_auth_draft
    from app.routes.auth.duplicate import duplicate_auth
    from app.routes.auth.export import export_auths
    from app.routes.auth.get import get_auth
    from app.routes.auth.search import search_auth
    from app.routes.auth.update import update_auth

    return ComposedContextResponse(
        name="auth",
        type="artifact",
        description=(
            "Auth providers define authentication configurations. "
            "Each auth links to resources (names, descriptions, departments, "
            "flags, items, protocols, slugs) via junction tables."
        ),
        artifact=(artifact if schema else None),
        entries=([drafts] if schema else None),
        resources=([
            names,
            descriptions,
            departments,
            flags,
            items,
            protocols,
            slugs,
        ] if schema else None),
        permission_docs=([
            get_operation_info(
                has_access,
                description="View access — any authenticated profile can view auths.",
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
                get_auth,
                description="POST /get — Get a single auth by ID with hydrated resources.",
            ),
            get_operation_info(
                search_auth,
                description="POST /search — Paginated auth search with filters.",
            ),
            get_operation_info(
                create_auth,
                description="POST /create — Create a new auth artifact.",
            ),
            get_operation_info(
                update_auth,
                description="POST /update — Update an existing auth's resource links.",
            ),
            get_operation_info(
                duplicate_auth,
                description="POST /duplicate — Duplicate an existing auth.",
            ),
            get_operation_info(
                delete_auth,
                description="POST /delete — Delete an auth.",
            ),
            get_operation_info(
                patch_auth_draft,
                description="PATCH /draft — Create or patch an auth draft (autosave).",
            ),
            get_operation_info(
                export_auths,
                description="POST /export — Export auths as denormalized CSV.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
