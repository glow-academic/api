"""Department docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — department_artifact table + CRUD operations
  3. Entry tool docs — department_drafts MV, tables, operations
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
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Department docs using composable infra functions.

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

    async def _dept_docs() -> object:
        async with pool.acquire() as conn:
            return await get_department_docs(conn)

    async def _drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_department_drafts_docs(conn)

    async def _names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _settings_docs() -> object:
        async with pool.acquire() as conn:
            return await get_settings_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        flags,
        settings,
    ) = await asyncio.gather(
        _dept_docs(),
        _drafts_docs(),
        _names_docs(),
        _descriptions_docs(),
        _flags_docs(),
        _settings_docs(),
    )

    # ── Step 3: Page metadata ───────────────────────────────────────────
    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)
    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # ── Step 4: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.department.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.department.create import create_department
    from app.routes.v5.department.delete import delete_department
    from app.routes.v5.department.draft import patch_department_draft
    from app.routes.v5.department.duplicate import duplicate_department
    from app.routes.v5.department.export import export_departments
    from app.routes.v5.department.get import get_department
    from app.routes.v5.department.search import search_department
    from app.routes.v5.department.update import update_department

    return ComposedDocsResponse(
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
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the department.",
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
    )
