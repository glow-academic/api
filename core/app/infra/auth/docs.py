"""Auth docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — auth_artifact table + CRUD operations
  3. Entry tool docs — auth_drafts MV, tables, operations
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
    async with pool.acquire() as conn:
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def docs_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Auth docs using composable infra functions.

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

    async def _fetch_auth_docs() -> object:
        async with pool.acquire() as c:
            return await get_auth_docs(c)

    async def _fetch_auth_drafts_docs() -> object:
        async with pool.acquire() as c:
            return await get_auth_drafts_docs(c)

    async def _fetch_names_docs() -> object:
        async with pool.acquire() as c:
            return await get_names_docs(c)

    async def _fetch_descriptions_docs() -> object:
        async with pool.acquire() as c:
            return await get_descriptions_docs(c)

    async def _fetch_departments_docs() -> object:
        async with pool.acquire() as c:
            return await get_departments_docs(c)

    async def _fetch_flags_docs() -> object:
        async with pool.acquire() as c:
            return await get_flags_docs(c)

    async def _fetch_items_docs() -> object:
        async with pool.acquire() as c:
            return await get_items_docs(c)

    async def _fetch_protocols_docs() -> object:
        async with pool.acquire() as c:
            return await get_protocols_docs(c)

    async def _fetch_slugs_docs() -> object:
        async with pool.acquire() as c:
            return await get_slugs_docs(c)

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
    )

    # ── Step 3: Page metadata ───────────────────────────────────────────
    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)
    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # ── Step 4: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.auth.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.auth.create import create_auth
    from app.routes.v5.auth.delete import delete_auth
    from app.routes.v5.auth.draft import patch_auth_draft
    from app.routes.v5.auth.duplicate import duplicate_auth
    from app.routes.v5.auth.export import export_auths
    from app.routes.v5.auth.get import get_auth
    from app.routes.v5.auth.search import search_auth
    from app.routes.v5.auth.update import update_auth

    return ComposedDocsResponse(
        name="auth",
        type="artifact",
        description=(
            "Auth providers define authentication configurations. "
            "Each auth links to resources (names, descriptions, departments, "
            "flags, items, protocols, slugs) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            departments,
            flags,
            items,
            protocols,
            slugs,
        ],
        permissions=[
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
        ],
        api_operations=[
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
        ],
        page_metadata=page_metadata,
    )
