"""Provider docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — provider_artifact table + CRUD operations
  3. Entry tool docs — provider_drafts MV, tables, operations
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
from app.tools.resources.names.get import get_names
from app.tools.resources.values.docs import get_values_docs

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
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Provider docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → profile check
      2. Parallel: artifact docs + entry docs + all resource docs
      3. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Parallel docs fetches ──────────────────────────────────

    async def _get_provider_docs() -> object:
        async with pool.acquire() as conn:
            return await get_provider_docs(conn)

    async def _get_provider_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_provider_drafts_docs(conn)

    async def _get_names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_endpoints_docs() -> object:
        async with pool.acquire() as conn:
            return await get_endpoints_docs(conn)

    async def _get_keys_docs() -> object:
        async with pool.acquire() as conn:
            return await get_keys_docs(conn)

    async def _get_values_docs() -> object:
        async with pool.acquire() as conn:
            return await get_values_docs(conn)

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
    )

    # ── Step 3: Page metadata ───────────────────────────────────────────

    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # ── Step 4: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.provider.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.provider.create import create_provider
    from app.routes.v5.provider.delete import delete_provider
    from app.routes.v5.provider.draft import patch_provider_draft
    from app.routes.v5.provider.duplicate import duplicate_provider
    from app.routes.v5.provider.export import export_providers
    from app.routes.v5.provider.get import get_provider
    from app.routes.v5.provider.search import search_provider
    from app.routes.v5.provider.update import update_provider

    return ComposedDocsResponse(
        name="provider",
        type="artifact",
        description=(
            "Providers define AI service provider configurations. "
            "Each provider links to resources (names, descriptions, departments, "
            "endpoints, flags, keys, values) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            flags,
            departments,
            endpoints,
            keys,
            values,
        ],
        permissions=[
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
        ],
        api_operations=[
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
        ],
        page_metadata=page_metadata,
    )
