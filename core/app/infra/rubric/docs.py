"""Rubric docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — rubric_artifact table + CRUD operations
  3. Entry tool docs — rubric_drafts MV, tables, operations
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
from app.tools.artifacts.rubric.docs import get_rubric_docs
from app.tools.artifacts.rubric.get import (
    get_rubrics as get_rubric_artifacts,
)

# Entry tool docs
from app.tools.entries.rubric_drafts.docs import get_rubric_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs
from app.tools.resources.names.get import get_names
from app.tools.resources.points.docs import get_points_docs
from app.tools.resources.standard_groups.docs import (
    get_standard_groups_docs,
)
from app.tools.resources.standards.docs import get_standards_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Rubrics",
    list_description="Manage evaluation criteria with scoring standards.",
    detail_title="— Rubric",
    detail_description="View and edit rubric configuration and linked resources.",
    new_title="New Rubric",
    new_description="Create a new evaluation rubric.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a rubric by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_rubric_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Rubric docs using composable infra functions.

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

    async def _get_rubric_docs() -> object:
        async with pool.acquire() as conn:
            return await get_rubric_docs(conn)

    async def _get_rubric_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_rubric_drafts_docs(conn)

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

    async def _get_points_docs() -> object:
        async with pool.acquire() as conn:
            return await get_points_docs(conn)

    async def _get_standard_groups_docs() -> object:
        async with pool.acquire() as conn:
            return await get_standard_groups_docs(conn)

    async def _get_standards_docs() -> object:
        async with pool.acquire() as conn:
            return await get_standards_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        flags,
        departments,
        points,
        standard_groups,
        standards,
    ) = await asyncio.gather(
        _get_rubric_docs(),
        _get_rubric_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_flags_docs(),
        _get_departments_docs(),
        _get_points_docs(),
        _get_standard_groups_docs(),
        _get_standards_docs(),
    )

    # ── Step 3: Page metadata ───────────────────────────────────────────

    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # ── Step 4: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.rubric.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.rubric.create import create_rubric
    from app.routes.v5.rubric.delete import delete_rubric
    from app.routes.v5.rubric.draft import patch_rubric_draft
    from app.routes.v5.rubric.duplicate import duplicate_rubric
    from app.routes.v5.rubric.export import export_rubrics
    from app.routes.v5.rubric.get import get_rubric
    from app.routes.v5.rubric.search import search_rubric
    from app.routes.v5.rubric.update import update_rubric

    return ComposedDocsResponse(
        name="rubric",
        type="artifact",
        description=(
            "Rubrics define evaluation criteria with scoring standards. "
            "Each rubric links to resources (names, descriptions, departments, "
            "flags, points, standard_groups, standards) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            flags,
            departments,
            points,
            standard_groups,
            standards,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the rubric.",
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
                get_rubric,
                description="POST /get — Get a single rubric by ID with hydrated resources.",
            ),
            get_operation_info(
                search_rubric,
                description="POST /search — Paginated rubric search with filters.",
            ),
            get_operation_info(
                create_rubric,
                description="POST /create — Create a new rubric artifact.",
            ),
            get_operation_info(
                update_rubric,
                description="POST /update — Update an existing rubric's resource links.",
            ),
            get_operation_info(
                duplicate_rubric,
                description="POST /duplicate — Duplicate an existing rubric.",
            ),
            get_operation_info(
                delete_rubric,
                description="POST /delete — Delete a rubric.",
            ),
            get_operation_info(
                patch_rubric_draft,
                description="PATCH /draft — Create or patch a rubric draft (autosave).",
            ),
            get_operation_info(
                export_rubrics,
                description="POST /export — Export rubrics as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
