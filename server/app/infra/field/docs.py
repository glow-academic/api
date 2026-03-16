"""Field docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — field_artifact table + CRUD operations
  3. Entry tool docs — field_drafts MV, tables, operations
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
from app.tools.artifacts.field.docs import get_field_docs
from app.tools.artifacts.field.get import get_fields as get_field_artifacts

# Entry tool docs
from app.tools.entries.field_drafts.docs import get_field_drafts_docs

# Resource tool docs
from app.tools.resources.conditional_parameters.docs import (
    get_conditional_parameters_docs,
)
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.parameters.docs import get_parameters_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Fields",
    list_description="Manage form field configurations.",
    detail_title="— Field",
    detail_description="View and edit field configuration and linked resources.",
    new_title="New Field",
    new_description="Create a new field.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a field by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_field_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def docs_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Field docs using composable infra functions.

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

    async def _get_field_docs() -> object:
        async with pool.acquire() as conn:
            return await get_field_docs(conn)

    async def _get_field_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_field_drafts_docs(conn)

    async def _get_names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_conditional_parameters_docs() -> object:
        async with pool.acquire() as conn:
            return await get_conditional_parameters_docs(conn)

    async def _get_departments_docs() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_parameters_docs() -> object:
        async with pool.acquire() as conn:
            return await get_parameters_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        conditional_parameters,
        departments,
        flags,
        parameters,
    ) = await asyncio.gather(
        _get_field_docs(),
        _get_field_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_conditional_parameters_docs(),
        _get_departments_docs(),
        _get_flags_docs(),
        _get_parameters_docs(),
    )

    # -- Step 3: Page metadata ───────────────────────────────────────────
    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)
    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Assemble response ---------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.field.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.field.create import create_field
    from app.routes.v5.field.delete import delete_field
    from app.routes.v5.field.draft import patch_field_draft
    from app.routes.v5.field.duplicate import duplicate_field
    from app.routes.v5.field.export import export_fields
    from app.routes.v5.field.get import get_field
    from app.routes.v5.field.search import search_field
    from app.routes.v5.field.update import update_field

    return ComposedDocsResponse(
        name="field",
        type="artifact",
        description=(
            "Fields define form field configurations. "
            "Each field links to resources (names, descriptions, departments, "
            "flags, parameters, conditional_parameters) "
            "via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            conditional_parameters,
            departments,
            flags,
            parameters,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the field.",
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
                get_field,
                description="POST /get — Get a single field by ID with hydrated resources.",
            ),
            get_operation_info(
                search_field,
                description="POST /search — Paginated field search with filters.",
            ),
            get_operation_info(
                create_field,
                description="POST /create — Create a new field artifact.",
            ),
            get_operation_info(
                update_field,
                description="POST /update — Update an existing field's resource links.",
            ),
            get_operation_info(
                duplicate_field,
                description="POST /duplicate — Duplicate an existing field.",
            ),
            get_operation_info(
                delete_field,
                description="POST /delete — Delete a field.",
            ),
            get_operation_info(
                patch_field_draft,
                description="PATCH /draft — Create or patch a field draft (autosave).",
            ),
            get_operation_info(
                export_fields,
                description="POST /export — Export fields as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
