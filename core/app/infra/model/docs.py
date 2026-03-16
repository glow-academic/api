"""Model docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — model_artifact table + CRUD operations
  3. Entry tool docs — model_drafts MV, tables, operations
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
from app.tools.artifacts.model.docs import get_model_docs
from app.tools.artifacts.model.get import get_models as get_model_artifacts

# Entry tool docs
from app.tools.entries.model_drafts.docs import get_model_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.modalities.docs import get_modalities_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.pricing.docs import get_pricing_docs
from app.tools.resources.providers.docs import get_providers_docs
from app.tools.resources.qualities.docs import get_qualities_docs
from app.tools.resources.reasoning_levels.docs import (
    get_reasoning_levels_docs,
)
from app.tools.resources.temperature_levels.docs import (
    get_temperature_levels_docs,
)
from app.tools.resources.values.docs import get_values_docs
from app.tools.resources.voices.docs import get_voices_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Models",
    list_description="Manage AI model configurations.",
    detail_title="— Model",
    detail_description="View and edit model configuration and linked resources.",
    new_title="New Model",
    new_description="Create a new model.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a model by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_model_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Model docs using composable infra functions.

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

    async def _get_model_docs() -> object:
        async with pool.acquire() as conn:
            return await get_model_docs(conn)

    async def _get_model_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_model_drafts_docs(conn)

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

    async def _get_modalities_docs() -> object:
        async with pool.acquire() as conn:
            return await get_modalities_docs(conn)

    async def _get_pricing_docs() -> object:
        async with pool.acquire() as conn:
            return await get_pricing_docs(conn)

    async def _get_providers_docs() -> object:
        async with pool.acquire() as conn:
            return await get_providers_docs(conn)

    async def _get_qualities_docs() -> object:
        async with pool.acquire() as conn:
            return await get_qualities_docs(conn)

    async def _get_reasoning_levels_docs() -> object:
        async with pool.acquire() as conn:
            return await get_reasoning_levels_docs(conn)

    async def _get_temperature_levels_docs() -> object:
        async with pool.acquire() as conn:
            return await get_temperature_levels_docs(conn)

    async def _get_values_docs() -> object:
        async with pool.acquire() as conn:
            return await get_values_docs(conn)

    async def _get_voices_docs() -> object:
        async with pool.acquire() as conn:
            return await get_voices_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        departments,
        flags,
        modalities,
        pricing,
        providers,
        qualities,
        reasoning_levels,
        temperature_levels,
        values,
        voices,
    ) = await asyncio.gather(
        _get_model_docs(),
        _get_model_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_departments_docs(),
        _get_flags_docs(),
        _get_modalities_docs(),
        _get_pricing_docs(),
        _get_providers_docs(),
        _get_qualities_docs(),
        _get_reasoning_levels_docs(),
        _get_temperature_levels_docs(),
        _get_values_docs(),
        _get_voices_docs(),
    )

    # -- Step 3: Page metadata ───────────────────────────────────────────
    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)
    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Assemble response ---------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.model.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.model.create import create_model
    from app.routes.v5.model.delete import delete_model
    from app.routes.v5.model.draft import patch_model_draft
    from app.routes.v5.model.duplicate import duplicate_model
    from app.routes.v5.model.export import export_models
    from app.routes.v5.model.get import get_model
    from app.routes.v5.model.search import search_model
    from app.routes.v5.model.update import update_model

    return ComposedDocsResponse(
        name="model",
        type="artifact",
        description=(
            "Models define AI model configurations. "
            "Each model links to resources (names, descriptions, departments, "
            "flags, modalities, pricing, providers, qualities, reasoning_levels, "
            "temperature_levels, values, voices) "
            "via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            departments,
            flags,
            modalities,
            pricing,
            providers,
            qualities,
            reasoning_levels,
            temperature_levels,
            values,
            voices,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the model.",
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
                get_model,
                description="POST /get — Get a single model by ID with hydrated resources.",
            ),
            get_operation_info(
                search_model,
                description="POST /search — Paginated model search with filters.",
            ),
            get_operation_info(
                create_model,
                description="POST /create — Create a new model artifact.",
            ),
            get_operation_info(
                update_model,
                description="POST /update — Update an existing model's resource links.",
            ),
            get_operation_info(
                duplicate_model,
                description="POST /duplicate — Duplicate an existing model.",
            ),
            get_operation_info(
                delete_model,
                description="POST /delete — Delete a model.",
            ),
            get_operation_info(
                patch_model_draft,
                description="PATCH /draft — Create or patch a model draft (autosave).",
            ),
            get_operation_info(
                export_models,
                description="POST /export — Export models as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
