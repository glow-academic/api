"""Profile docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — profile_artifact table + CRUD operations
  3. Entry tool docs — profile_drafts MV, tables, operations
  4. Resource tool docs — all linked resources (names, emails, etc.)
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
from app.tools.resources.names.get import get_names
from app.tools.resources.request_limits.docs import get_request_limits_docs
from app.tools.resources.roles.docs import get_roles_docs

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
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Profile docs using composable infra functions.

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

    async def _get_profile_docs() -> object:
        async with pool.acquire() as conn:
            return await get_profile_docs(conn)

    async def _get_profile_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_profile_drafts_docs(conn)

    async def _get_names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_emails_docs() -> object:
        async with pool.acquire() as conn:
            return await get_emails_docs(conn)

    async def _get_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_request_limits_docs() -> object:
        async with pool.acquire() as conn:
            return await get_request_limits_docs(conn)

    async def _get_roles_docs() -> object:
        async with pool.acquire() as conn:
            return await get_roles_docs(conn)

    (
        artifact,
        drafts,
        names,
        emails,
        flags,
        departments,
        request_limits,
        roles,
    ) = await asyncio.gather(
        _get_profile_docs(),
        _get_profile_drafts_docs(),
        _get_names_docs(),
        _get_emails_docs(),
        _get_flags_docs(),
        _get_departments_docs(),
        _get_request_limits_docs(),
        _get_roles_docs(),
    )

    # ── Step 3: Page metadata ───────────────────────────────────────────

    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # ── Step 4: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.profile.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.profile.create import create_profile
    from app.routes.v5.profile.delete import delete_profile
    from app.routes.v5.profile.draft import patch_profile_draft
    from app.routes.v5.profile.duplicate import duplicate_profile
    from app.routes.v5.profile.export import export_profiles
    from app.routes.v5.profile.get import get_profile
    from app.routes.v5.profile.search import search_profile
    from app.routes.v5.profile.update import update_profile

    return ComposedDocsResponse(
        name="profile",
        type="artifact",
        description=(
            "Profiles define user accounts and permissions. "
            "Each profile links to resources (names, departments, emails, "
            "flags, request_limits, roles) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            emails,
            flags,
            departments,
            request_limits,
            roles,
        ],
        permissions=[
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
        ],
        api_operations=[
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
        ],
        page_metadata=page_metadata,
    )
