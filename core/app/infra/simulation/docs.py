"""Simulation docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — simulation_artifact table + CRUD operations
  3. Entry tool docs — simulation_drafts MV, tables, operations
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
from app.tools.artifacts.simulation.docs import get_simulation_docs
from app.tools.artifacts.simulation.get import (
    get_simulations as get_simulation_artifacts,
)

# Entry tool docs
from app.tools.entries.simulation_drafts.docs import (
    get_simulation_drafts_docs,
)

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs
from app.tools.resources.names.get import get_names
from app.tools.resources.rubrics.docs import get_rubrics_docs
from app.tools.resources.scenario_flags.docs import get_scenario_flags_docs
from app.tools.resources.scenario_positions.docs import (
    get_scenario_positions_docs,
)
from app.tools.resources.scenario_rubrics.docs import (
    get_scenario_rubrics_docs,
)
from app.tools.resources.scenario_time_limits.docs import (
    get_scenario_time_limits_docs,
)
from app.tools.resources.scenarios.docs import get_scenarios_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Simulations",
    list_description="Manage assessment experiences combining scenarios.",
    detail_title="— Simulation",
    detail_description="View and edit simulation configuration and linked resources.",
    new_title="New Simulation",
    new_description="Create a new simulation assessment.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a simulation by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_simulation_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Simulation docs using composable infra functions.

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

    async def _doc_simulation() -> object:
        async with pool.acquire() as conn:
            return await get_simulation_docs(conn)

    async def _doc_drafts() -> object:
        async with pool.acquire() as conn:
            return await get_simulation_drafts_docs(conn)

    async def _doc_names() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _doc_descriptions() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _doc_departments() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _doc_flags() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _doc_rubrics() -> object:
        async with pool.acquire() as conn:
            return await get_rubrics_docs(conn)

    async def _doc_scenario_flags() -> object:
        async with pool.acquire() as conn:
            return await get_scenario_flags_docs(conn)

    async def _doc_scenario_positions() -> object:
        async with pool.acquire() as conn:
            return await get_scenario_positions_docs(conn)

    async def _doc_scenario_rubrics() -> object:
        async with pool.acquire() as conn:
            return await get_scenario_rubrics_docs(conn)

    async def _doc_scenario_time_limits() -> object:
        async with pool.acquire() as conn:
            return await get_scenario_time_limits_docs(conn)

    async def _doc_scenarios() -> object:
        async with pool.acquire() as conn:
            return await get_scenarios_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        departments,
        flags,
        rubrics,
        scenario_flags,
        scenario_positions,
        scenario_rubrics,
        scenario_time_limits,
        scenarios,
    ) = await asyncio.gather(
        _doc_simulation(),
        _doc_drafts(),
        _doc_names(),
        _doc_descriptions(),
        _doc_departments(),
        _doc_flags(),
        _doc_rubrics(),
        _doc_scenario_flags(),
        _doc_scenario_positions(),
        _doc_scenario_rubrics(),
        _doc_scenario_time_limits(),
        _doc_scenarios(),
    )

    # -- Step 3: Page metadata ---------------------------------------------------

    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Assemble response ---------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.simulation.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.simulation.create import create_simulation
    from app.routes.v5.simulation.delete import delete_simulation
    from app.routes.v5.simulation.draft import patch_simulation_draft
    from app.routes.v5.simulation.duplicate import duplicate_simulation
    from app.routes.v5.simulation.export import export_simulations
    from app.routes.v5.simulation.get import get_simulation
    from app.routes.v5.simulation.search import search_simulation
    from app.routes.v5.simulation.update import update_simulation

    return ComposedDocsResponse(
        name="simulation",
        type="artifact",
        description=(
            "Simulations define assessment experiences combining scenarios. "
            "Each simulation links to resources (names, descriptions, departments, "
            "flags, rubrics, scenarios, scenario_flags, scenario_positions, "
            "scenario_rubrics, scenario_time_limits) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            departments,
            flags,
            rubrics,
            scenario_flags,
            scenario_positions,
            scenario_rubrics,
            scenario_time_limits,
            scenarios,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the simulation.",
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
                get_simulation,
                description="POST /get — Get a single simulation by ID with hydrated resources.",
            ),
            get_operation_info(
                search_simulation,
                description="POST /search — Paginated simulation search with filters.",
            ),
            get_operation_info(
                create_simulation,
                description="POST /create — Create a new simulation artifact.",
            ),
            get_operation_info(
                update_simulation,
                description="POST /update — Update an existing simulation's resource links.",
            ),
            get_operation_info(
                duplicate_simulation,
                description="POST /duplicate — Duplicate an existing simulation.",
            ),
            get_operation_info(
                delete_simulation,
                description="POST /delete — Delete a simulation.",
            ),
            get_operation_info(
                patch_simulation_draft,
                description="PATCH /draft — Create or patch a simulation draft (autosave).",
            ),
            get_operation_info(
                export_simulations,
                description="POST /export — Export simulations as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
