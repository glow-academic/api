"""Cohort docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — cohort_artifact table + CRUD operations
  3. Entry tool docs — cohort_drafts MV, tables, operations
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
from app.tools.artifacts.cohort.docs import get_cohort_docs
from app.tools.artifacts.cohort.get import get_cohorts as get_cohort_artifacts

# Entry tool docs
from app.tools.entries.cohort_drafts.docs import get_cohort_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.personas.docs import get_personas_docs
from app.tools.resources.profile_personas.docs import (
    get_profile_personas_docs,
)
from app.tools.resources.profiles.docs import get_profiles_docs
from app.tools.resources.simulation_availability.docs import (
    get_simulation_availability_docs,
)
from app.tools.resources.simulation_positions.docs import (
    get_simulation_positions_docs,
)
from app.tools.resources.simulations.docs import get_simulations_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Cohorts",
    list_description="Manage groups of profiles assigned to simulations.",
    detail_title="— Cohort",
    detail_description="View and edit cohort configuration and linked resources.",
    new_title="New Cohort",
    new_description="Create a new cohort.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a cohort by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_cohort_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Cohort docs using composable infra functions.

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

    async def _fetch_cohort_docs() -> object:
        async with pool.acquire() as conn:
            return await get_cohort_docs(conn)

    async def _fetch_cohort_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_cohort_drafts_docs(conn)

    async def _fetch_names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _fetch_descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _fetch_departments_docs() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _fetch_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _fetch_personas_docs() -> object:
        async with pool.acquire() as conn:
            return await get_personas_docs(conn)

    async def _fetch_profile_personas_docs() -> object:
        async with pool.acquire() as conn:
            return await get_profile_personas_docs(conn)

    async def _fetch_profiles_docs() -> object:
        async with pool.acquire() as conn:
            return await get_profiles_docs(conn)

    async def _fetch_simulations_docs() -> object:
        async with pool.acquire() as conn:
            return await get_simulations_docs(conn)

    async def _fetch_simulation_availability_docs() -> object:
        async with pool.acquire() as conn:
            return await get_simulation_availability_docs(conn)

    async def _fetch_simulation_positions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_simulation_positions_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        departments,
        flags,
        personas,
        profile_personas,
        profiles,
        simulations,
        simulation_availability,
        simulation_positions,
    ) = await asyncio.gather(
        _fetch_cohort_docs(),
        _fetch_cohort_drafts_docs(),
        _fetch_names_docs(),
        _fetch_descriptions_docs(),
        _fetch_departments_docs(),
        _fetch_flags_docs(),
        _fetch_personas_docs(),
        _fetch_profile_personas_docs(),
        _fetch_profiles_docs(),
        _fetch_simulations_docs(),
        _fetch_simulation_availability_docs(),
        _fetch_simulation_positions_docs(),
    )

    # ── Step 3: Page metadata ───────────────────────────────────────────
    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)
    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # ── Step 4: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.cohort.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.cohort.create import create_cohort
    from app.routes.v5.cohort.delete import delete_cohort
    from app.routes.v5.cohort.draft import patch_cohort_draft
    from app.routes.v5.cohort.duplicate import duplicate_cohort
    from app.routes.v5.cohort.export import export_cohorts
    from app.routes.v5.cohort.get import get_cohort
    from app.routes.v5.cohort.search import search_cohort
    from app.routes.v5.cohort.update import update_cohort

    return ComposedDocsResponse(
        name="cohort",
        type="artifact",
        description=(
            "Cohorts define groups of profiles assigned to simulations. "
            "Each cohort links to resources (names, descriptions, departments, "
            "flags, personas, profiles, profile_personas, simulations, "
            "simulation_availability, simulation_positions) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            departments,
            flags,
            personas,
            profile_personas,
            profiles,
            simulations,
            simulation_availability,
            simulation_positions,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the cohort.",
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
                get_cohort,
                description="POST /get — Get a single cohort by ID with hydrated resources.",
            ),
            get_operation_info(
                search_cohort,
                description="POST /search — Paginated cohort search with filters.",
            ),
            get_operation_info(
                create_cohort,
                description="POST /create — Create a new cohort artifact.",
            ),
            get_operation_info(
                update_cohort,
                description="POST /update — Update an existing cohort's resource links.",
            ),
            get_operation_info(
                duplicate_cohort,
                description="POST /duplicate — Duplicate an existing cohort.",
            ),
            get_operation_info(
                delete_cohort,
                description="POST /delete — Delete a cohort.",
            ),
            get_operation_info(
                patch_cohort_draft,
                description="PATCH /draft — Create or patch a cohort draft (autosave).",
            ),
            get_operation_info(
                export_cohorts,
                description="POST /export — Export cohorts as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
