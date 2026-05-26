"""Provider page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the provider page:
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
from app.infra.server_timing import timed

# Artifact tool docs
from app.tools.artifacts.provider.docs import get_provider_docs
from app.tools.artifacts.provider.get import (
    get_providers as get_provider_artifacts,
)

# Entry tool docs
from app.tools.entries.provider_drafts.docs import get_provider_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.endpoints.docs import get_endpoints_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.keys.docs import get_keys_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.values.docs import get_values_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Providers",
    list_description="Manage AI service provider configurations.",
    detail_title="— Provider",
    detail_description="View and edit provider configuration and linked resources.",
    new_title="New Provider",
    new_description="Create a new AI service provider configuration.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a provider by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_provider_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """provider page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("provider/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "provider", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_provider_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_provider_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Provider page context.

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

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches + entity resolution ----------------------
    # Each branch acquires its own connection from the pool.

    async def _get_provider_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_provider_docs(conn)

    async def _get_provider_drafts_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_provider_drafts_docs(conn)

    async def _get_names_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

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

    async def _get_endpoints_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_endpoints_docs(conn)

    async def _get_keys_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_keys_docs(conn)

    async def _get_values_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_values_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.provider.permissions_context import (
            resolve_provider_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_provider_permissions_context(conn, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

    with timed("docs"):
        (
            artifact,
            drafts,
            names,
            descriptions,
            flags,
            departments,
            endpoints,
            keys,
            values,
            entity_perms,
            entity_name,
        ) = await asyncio.gather(
            _get_provider_docs(),
            _get_provider_drafts_docs(),
            _get_names_docs(),
            _get_descriptions_docs(),
            _get_flags_docs(),
            _get_departments_docs(),
            _get_endpoints_docs(),
            _get_keys_docs(),
            _get_values_docs(),
            _get_entity_perms(),
            _get_entity_name(),
        )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.provider.permissions import (
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
            entity_perms.active_model_count,
            profile.department_ids,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_model_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_model_count,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    with timed("profile_summary"):
        profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Configure a provider", content="Create a new AI provider configuration with API endpoint and credentials."),
            StarterPrompt(title="From API docs", content="I have API documentation — help me configure a provider from it."),
            StarterPrompt(title="Template-based", content="Create a provider from a common template like OpenAI, Anthropic, or custom endpoint."),
        ],
        "search": [
            StarterPrompt(title="Find providers", content="Help me find providers that match specific capabilities or rate limit requirements."),
            StarterPrompt(title="Compare providers", content="Compare my provider configurations and identify gaps in coverage or redundancies."),
            StarterPrompt(title="Audit providers", content="Review all providers and flag any with missing credentials or outdated endpoints."),
        ],
        "update": [
            StarterPrompt(title="Optimize settings", content="Fine-tune this provider's timeout, retry, and concurrency settings."),
            StarterPrompt(title="Update credentials", content="Update this provider's API keys and endpoint configuration."),
            StarterPrompt(title="Add rate limits", content="Configure rate limits and failover settings for this provider."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone provider", content="Duplicate this provider and modify its endpoint for a different environment."),
            StarterPrompt(title="Staging copy", content="Create a staging version of this provider with separate credentials."),
        ],
        "draft": [
            StarterPrompt(title="Draft provider", content="Start drafting a new provider — suggest an endpoint and key configuration."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements to the API settings before saving."),
        ],
        "export": [
            StarterPrompt(title="Export inventory", content="Generate a summary of all providers with their endpoints and status."),
            StarterPrompt(title="Export analysis", content="Analyze my providers and create a report on coverage and rate limit configurations."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.provider.create import create_provider
    from app.routes.provider.delete import delete_provider
    from app.routes.provider.draft import patch_provider_draft
    from app.routes.provider.duplicate import duplicate_provider
    from app.routes.provider.export import export_providers
    from app.routes.provider.get import get_provider
    from app.routes.provider.search import search_provider
    from app.routes.provider.update import update_provider

    return ComposedContextResponse(
        name="provider",
        type="artifact",
        description=(
            "Providers define AI service provider configurations. "
            "Each provider links to resources (names, descriptions, departments, "
            "endpoints, flags, keys, values) via junction tables."
        ),
        artifact=(artifact if schema else None),
        entries=([drafts] if schema else None),
        resources=([
            names,
            descriptions,
            flags,
            departments,
            endpoints,
            keys,
            values,
        ] if schema else None),
        permission_docs=([
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the provider.",
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
                get_provider,
                description="POST /get — Get a single provider by ID with hydrated resources.",
            ),
            get_operation_info(
                search_provider,
                description="POST /search — Paginated provider search with filters.",
            ),
            get_operation_info(
                create_provider,
                description="POST /create — Create a new provider artifact.",
            ),
            get_operation_info(
                update_provider,
                description="POST /update — Update an existing provider's resource links.",
            ),
            get_operation_info(
                duplicate_provider,
                description="POST /duplicate — Duplicate an existing provider.",
            ),
            get_operation_info(
                delete_provider,
                description="POST /delete — Delete a provider.",
            ),
            get_operation_info(
                patch_provider_draft,
                description="PATCH /draft — Create or patch a provider draft (autosave).",
            ),
            get_operation_info(
                export_providers,
                description="POST /export — Export providers as denormalized CSV.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
