"""Setting docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — setting_artifact table + CRUD operations
  3. Entry tool docs — setting_drafts MV, tables, operations
  4. Resource tool docs — all linked resources (names, descriptions, etc.)
  5. Permission functions — introspected via get_operation_info
  6. API operations — all public route handlers introspected
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import ComposedDocsResponse
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
from app.tools.resources.auths.docs import get_auths_docs
from app.tools.resources.colors.docs import get_colors_docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs
from app.tools.resources.names.get import get_names
from app.tools.resources.profiles.docs import get_profiles_docs
from app.tools.resources.provider_keys.docs import get_provider_keys_docs
from app.tools.resources.systems.docs import get_systems_docs

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
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Setting docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Parallel: artifact docs + entry docs + all resource docs
      3. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context -----------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches -----------------------------------------

    async def _setting_docs() -> object:
        async with pool.acquire() as conn:
            return await get_setting_docs(conn)

    async def _drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_setting_drafts_docs(conn)

    async def _names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _auth_item_keys_docs() -> object:
        async with pool.acquire() as conn:
            return await get_auth_item_keys_docs(conn)

    async def _auths_docs() -> object:
        async with pool.acquire() as conn:
            return await get_auths_docs(conn)

    async def _colors_docs() -> object:
        async with pool.acquire() as conn:
            return await get_colors_docs(conn)

    async def _departments_docs() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _profiles_docs() -> object:
        async with pool.acquire() as conn:
            return await get_profiles_docs(conn)

    async def _provider_keys_docs() -> object:
        async with pool.acquire() as conn:
            return await get_provider_keys_docs(conn)

    async def _systems_docs() -> object:
        async with pool.acquire() as conn:
            return await get_systems_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        auth_item_keys,
        auths,
        colors,
        departments,
        flags,
        profiles,
        provider_keys,
        systems,
    ) = await asyncio.gather(
        _setting_docs(),
        _drafts_docs(),
        _names_docs(),
        _descriptions_docs(),
        _auth_item_keys_docs(),
        _auths_docs(),
        _colors_docs(),
        _departments_docs(),
        _flags_docs(),
        _profiles_docs(),
        _provider_keys_docs(),
        _systems_docs(),
    )

    # -- Step 3: Page metadata ---------------------------------------------------

    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Assemble response ---------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.setting.permissions import (
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.setting.create import create_setting
    from app.routes.v5.setting.delete import delete_setting
    from app.routes.v5.setting.draft import patch_setting_draft
    from app.routes.v5.setting.duplicate import duplicate_setting
    from app.routes.v5.setting.export import export_settings
    from app.routes.v5.setting.get import get_setting
    from app.routes.v5.setting.search import search_setting
    from app.routes.v5.setting.update import update_setting

    return ComposedDocsResponse(
        name="setting",
        type="artifact",
        description=(
            "Settings define system configuration and preferences. "
            "Each setting links to resources (names, descriptions, departments, "
            "flags, auths, auth_item_keys, colors, profiles, provider_keys, "
            "systems) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            auth_item_keys,
            auths,
            colors,
            departments,
            flags,
            profiles,
            provider_keys,
            systems,
        ],
        permissions=[
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
    )
