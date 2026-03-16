"""Parameter docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — parameter_artifact table + CRUD operations
  3. Entry tool docs — parameter_drafts MV, tables, operations
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
from app.infra.docs.types import ComposedDocsResponse, DocsResponse
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Artifact tool docs
from app.tools.artifacts.parameter.docs import get_parameter_docs
from app.tools.artifacts.parameter.get import (
    get_parameters as get_parameter_artifacts,
)

# Entry tool docs
from app.tools.entries.parameter_drafts.docs import get_parameter_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs
from app.tools.resources.names.get import get_names
from app.tools.resources.parameter_fields.docs import (
    get_parameter_fields_docs,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Parameters",
    list_description="Manage configurable parameter sets.",
    detail_title="— Parameter",
    detail_description="View and edit parameter configuration and linked resources.",
    new_title="New Parameter",
    new_description="Create a new parameter configuration.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a parameter by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_parameter_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Parameter docs using composable infra functions.

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

    async def _get_parameter_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_parameter_docs(conn)

    async def _get_drafts_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_parameter_drafts_docs(conn)

    async def _get_names_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_flags_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_parameter_fields_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_parameter_fields_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        flags,
        departments,
        parameter_fields,
    ) = await asyncio.gather(
        _get_parameter_docs(),
        _get_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_flags_docs(),
        _get_departments_docs(),
        _get_parameter_fields_docs(),
    )

    # ── Step 3: Page metadata ───────────────────────────────────────────

    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # ── Step 4: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.parameter.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.parameter.create import create_parameter
    from app.routes.v5.parameter.delete import delete_parameter
    from app.routes.v5.parameter.draft import patch_parameter_draft
    from app.routes.v5.parameter.duplicate import duplicate_parameter
    from app.routes.v5.parameter.export import export_parameters
    from app.routes.v5.parameter.get import get_parameter
    from app.routes.v5.parameter.search import search_parameter
    from app.routes.v5.parameter.update import update_parameter

    return ComposedDocsResponse(
        name="parameter",
        type="artifact",
        description=(
            "Parameters define configurable parameter sets. "
            "Each parameter links to resources (names, descriptions, departments, "
            "flags, parameter_fields) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            flags,
            departments,
            parameter_fields,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the parameter.",
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
                get_parameter,
                description="POST /get — Get a single parameter by ID with hydrated resources.",
            ),
            get_operation_info(
                search_parameter,
                description="POST /search — Paginated parameter search with filters.",
            ),
            get_operation_info(
                create_parameter,
                description="POST /create — Create a new parameter artifact.",
            ),
            get_operation_info(
                update_parameter,
                description="POST /update — Update an existing parameter's resource links.",
            ),
            get_operation_info(
                duplicate_parameter,
                description="POST /duplicate — Duplicate an existing parameter.",
            ),
            get_operation_info(
                delete_parameter,
                description="POST /delete — Delete a parameter.",
            ),
            get_operation_info(
                patch_parameter_draft,
                description="PATCH /draft — Create or patch a parameter draft (autosave).",
            ),
            get_operation_info(
                export_parameters,
                description="POST /export — Export parameters as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
