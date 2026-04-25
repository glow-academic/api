"""Setting page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the setting page:
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
from app.tools.artifacts.setting.docs import get_setting_docs
from app.tools.artifacts.setting.get import (
    get_settings as get_setting_artifacts,
)

# Entry tool docs
from app.tools.entries.setting_drafts.docs import get_setting_drafts_docs

# Resource tool docs
from app.tools.resources.auth_item_keys.docs import get_auth_item_keys_docs
from app.tools.resources.colors.docs import get_colors_docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.provider_keys.docs import get_provider_keys_docs
from app.tools.resources.systems.docs import get_systems_docs
from app.tools.resources.thresholds.docs import get_thresholds_docs

from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Settings",
    list_description="Manage system configuration and preferences.",
    detail_title="— Setting",
    detail_description="View and edit setting configuration and linked resources.",
    new_title="New Setting",
    new_description="Create a new system setting.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a setting by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_setting_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """setting page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("setting/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "setting", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_setting_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_setting_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Setting page context.

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

    async def _get_setting_docs() -> list:
        async with pool.acquire() as conn:
            return await get_setting_docs(conn)

    async def _get_setting_drafts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_setting_drafts_docs(conn)

    async def _get_names_docs() -> list:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_auth_item_keys_docs() -> list:
        async with pool.acquire() as conn:
            return await get_auth_item_keys_docs(conn)

    async def _get_colors_docs() -> list:
        async with pool.acquire() as conn:
            return await get_colors_docs(conn)

    async def _get_departments_docs() -> list:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_provider_keys_docs() -> list:
        async with pool.acquire() as conn:
            return await get_provider_keys_docs(conn)

    async def _get_systems_docs() -> list:
        async with pool.acquire() as conn:
            return await get_systems_docs(conn)

    async def _get_thresholds_docs() -> list:
        async with pool.acquire() as conn:
            return await get_thresholds_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.setting.permissions_context import (
            resolve_setting_permissions_context,
        )

        async with pool.acquire() as conn:
            return await resolve_setting_permissions_context(conn, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

    (
        artifact,
        drafts,
        names,
        descriptions,
        auth_item_keys,
        colors,
        departments,
        flags,
        provider_keys,
        systems,
        thresholds,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_setting_docs(),
        _get_setting_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_auth_item_keys_docs(),
        _get_colors_docs(),
        _get_departments_docs(),
        _get_flags_docs(),
        _get_provider_keys_docs(),
        _get_systems_docs(),
        _get_thresholds_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.setting.permissions import (
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        compute_disabled_reason,
        has_access,
    )

    caller_permissions = CallerPermissions(
        can_create=False,
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
            profile.department_ids,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            profile.department_ids,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Define a setting", content="Create a new system setting with appropriate defaults and constraints."),
            StarterPrompt(title="From requirements", content="I have specific configuration needs — help me define the right settings."),
            StarterPrompt(title="Template-based", content="Create a setting from a common pattern like feature flag, threshold, or policy."),
        ],
        "search": [
            StarterPrompt(title="Find settings", content="Help me find settings that control specific system behaviors or features."),
            StarterPrompt(title="Compare settings", content="Compare my settings and identify conflicting or redundant configurations."),
            StarterPrompt(title="Audit settings", content="Review all settings and flag any with missing defaults or unclear descriptions."),
        ],
        "update": [
            StarterPrompt(title="Adjust defaults", content="Update this setting's default value and constraints to match current requirements."),
            StarterPrompt(title="Add constraints", content="Add validation constraints and acceptable value ranges to this setting."),
            StarterPrompt(title="Review impact", content="Analyze the impact of changing this setting on system behavior."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone setting", content="Duplicate this setting and modify its constraints for a different environment."),
            StarterPrompt(title="Environment copy", content="Create a variant of this setting with different defaults for staging or production."),
        ],
        "draft": [
            StarterPrompt(title="Draft setting", content="Start drafting a new setting — suggest a name, default value, and constraints."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements to validation before saving."),
        ],
        "export": [
            StarterPrompt(title="Export configuration", content="Generate a summary of all settings with their current values and constraints."),
            StarterPrompt(title="Export analysis", content="Analyze my settings and create a report on configuration coverage and consistency."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.setting.create import create_setting
    from app.routes.setting.delete import delete_setting
    from app.routes.setting.draft import patch_setting_draft
    from app.routes.setting.duplicate import duplicate_setting
    from app.routes.setting.export import export_settings
    from app.routes.setting.get import get_setting
    from app.routes.setting.search import search_setting
    from app.routes.setting.update import update_setting

    return ComposedContextResponse(
        name="setting",
        type="artifact",
        description=(
            "Settings define system configuration and preferences. "
            "Each setting links to resources (names, descriptions, departments, "
            "flags, colors, logins, systems, mcp, thresholds, provider_keys, "
            "auth_item_keys, auth_item_values) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            auth_item_keys,
            colors,
            departments,
            flags,
            provider_keys,
            systems,
            thresholds,
        ],
        permission_docs=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the setting.",
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
                compute_can_draft,
                description="Draft — role-only check.",
            ),
        ],
        api_operations=[
            get_operation_info(
                get_setting,
                description="POST /get — Get a single setting by ID with hydrated resources.",
            ),
            get_operation_info(
                search_setting,
                description="POST /search — Paginated setting search with filters.",
            ),
            get_operation_info(
                create_setting,
                description="POST /create — Create a new setting artifact.",
            ),
            get_operation_info(
                update_setting,
                description="POST /update — Update an existing setting's resource links.",
            ),
            get_operation_info(
                duplicate_setting,
                description="POST /duplicate — Duplicate an existing setting.",
            ),
            get_operation_info(
                delete_setting,
                description="POST /delete — Delete a setting.",
            ),
            get_operation_info(
                patch_setting_draft,
                description="PATCH /draft — Create or patch a setting draft (autosave).",
            ),
            get_operation_info(
                export_settings,
                description="POST /export — Export settings as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
