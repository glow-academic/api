"""Eval docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — eval_artifact table + CRUD operations
  3. Entry tool docs — eval_drafts MV, tables, operations
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
from app.tools.artifacts.eval.docs import get_eval_docs
from app.tools.artifacts.eval.get import get_evals as get_eval_artifacts

# Entry tool docs
from app.tools.entries.eval_drafts.docs import get_eval_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.model_flags.docs import get_model_flags_docs
from app.tools.resources.model_positions.docs import get_model_positions_docs
from app.tools.resources.model_rubrics.docs import get_model_rubrics_docs
from app.tools.resources.models.docs import get_models_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names

_PAGE_METADATA = PageMetadataConfig(
    list_title="Evals",
    list_description="Manage evaluation configurations for model assessment.",
    detail_title="— Eval",
    detail_description="View and edit eval configuration and linked resources.",
    new_title="New Eval",
    new_description="Create a new eval.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for an eval by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_eval_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Eval docs using composable infra functions.

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

    async def _get_eval_docs() -> object:
        async with pool.acquire() as conn:
            return await get_eval_docs(conn)

    async def _get_eval_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_eval_drafts_docs(conn)

    async def _get_names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_departments_docs() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_model_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_model_flags_docs(conn)

    async def _get_model_positions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_model_positions_docs(conn)

    async def _get_model_rubrics_docs() -> object:
        async with pool.acquire() as conn:
            return await get_model_rubrics_docs(conn)

    async def _get_models_docs() -> object:
        async with pool.acquire() as conn:
            return await get_models_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        departments,
        flags,
        model_flags,
        model_positions,
        model_rubrics,
        models,
    ) = await asyncio.gather(
        _get_eval_docs(),
        _get_eval_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_departments_docs(),
        _get_flags_docs(),
        _get_model_flags_docs(),
        _get_model_positions_docs(),
        _get_model_rubrics_docs(),
        _get_models_docs(),
    )

    # -- Step 3: Page metadata ───────────────────────────────────────────
    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)
    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Assemble response ---------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.eval.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.eval.create import create_eval
    from app.routes.v5.eval.delete import delete_eval
    from app.routes.v5.eval.draft import patch_eval_draft
    from app.routes.v5.eval.duplicate import duplicate_eval
    from app.routes.v5.eval.export import export_evals
    from app.routes.v5.eval.get import get_eval
    from app.routes.v5.eval.search import search_eval
    from app.routes.v5.eval.update import update_eval

    return ComposedDocsResponse(
        name="eval",
        type="artifact",
        description=(
            "Evals define evaluation configurations for model assessment. "
            "Each eval links to resources (names, descriptions, departments, "
            "flags, models, model_flags, model_positions, model_rubrics) "
            "via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            departments,
            flags,
            model_flags,
            model_positions,
            model_rubrics,
            models,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the eval.",
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
                get_eval,
                description="POST /get — Get a single eval by ID with hydrated resources.",
            ),
            get_operation_info(
                search_eval,
                description="POST /search — Paginated eval search with filters.",
            ),
            get_operation_info(
                create_eval,
                description="POST /create — Create a new eval artifact.",
            ),
            get_operation_info(
                update_eval,
                description="POST /update — Update an existing eval's resource links.",
            ),
            get_operation_info(
                duplicate_eval,
                description="POST /duplicate — Duplicate an existing eval.",
            ),
            get_operation_info(
                delete_eval,
                description="POST /delete — Delete an eval.",
            ),
            get_operation_info(
                patch_eval_draft,
                description="PATCH /draft — Create or patch an eval draft (autosave).",
            ),
            get_operation_info(
                export_evals,
                description="POST /export — Export evals as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
