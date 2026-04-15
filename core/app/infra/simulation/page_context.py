"""Simulation page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the simulation page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Artifact/entry/resource docs — schema introspection (same as docs.py)
  3. Permission evaluation — concrete booleans for THIS caller
  4. Entity permissions — can_edit/can_delete when entity_id is provided
  5. Page metadata — titles and descriptions for list/detail/new views
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
)
from app.infra.docs.build_profile_summary import build_profile_summary
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

# Name hydration
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


async def page_context_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Simulation page context — superset of docs_simulation_impl.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: artifact docs + entry docs + all resource docs
         + entity permissions context (if entity_id)
         + entity name (if entity_id)
      3. Evaluate caller permissions using profile data
      4. Assemble ComposedContextResponse
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches + entity resolution ----------------------
    # Each branch acquires its own connection from the pool.

    async def _get_simulation_docs() -> list:
        async with pool.acquire() as conn:
            return await get_simulation_docs(conn)

    async def _get_simulation_drafts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_simulation_drafts_docs(conn)

    async def _get_names_docs() -> list:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_departments_docs() -> list:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_rubrics_docs() -> list:
        async with pool.acquire() as conn:
            return await get_rubrics_docs(conn)

    async def _get_scenario_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_scenario_flags_docs(conn)

    async def _get_scenario_positions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_scenario_positions_docs(conn)

    async def _get_scenario_rubrics_docs() -> list:
        async with pool.acquire() as conn:
            return await get_scenario_rubrics_docs(conn)

    async def _get_scenario_time_limits_docs() -> list:
        async with pool.acquire() as conn:
            return await get_scenario_time_limits_docs(conn)

    async def _get_scenarios_docs() -> list:
        async with pool.acquire() as conn:
            return await get_scenarios_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.simulation.permissions_context import (
            resolve_simulation_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_simulation_permissions_context(conn, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

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
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_simulation_docs(),
        _get_simulation_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_departments_docs(),
        _get_flags_docs(),
        _get_rubrics_docs(),
        _get_scenario_flags_docs(),
        _get_scenario_positions_docs(),
        _get_scenario_rubrics_docs(),
        _get_scenario_time_limits_docs(),
        _get_scenarios_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.simulation.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        compute_disabled_reason,
        has_access,
    )

    caller_permissions = CallerPermissions(
        can_create=compute_can_create(
            profile.role_level,
            profile.role_permissions,
            profile.department_ids,
        ),
        can_draft=compute_can_draft(
            profile.role_level,
            profile.role_permissions,
        ),
        can_duplicate=compute_can_duplicate(
            profile.role_level,
            profile.role_permissions,
        ),
    )

    # Entity-level permissions (only when entity_id was provided and found)
    if entity_id and entity_perms and entity_perms.exists:
        caller_permissions.has_access = has_access(
            profile.role_level,
            profile.department_ids,
            entity_perms.department_ids,
        )
        caller_permissions.can_edit = compute_can_edit(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.cohort_usage_count,
            profile.department_ids,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.cohort_usage_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.cohort_usage_count,
            profile.department_ids,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.simulation.create import create_simulation
    from app.routes.simulation.delete import delete_simulation
    from app.routes.simulation.draft import patch_simulation_draft
    from app.routes.simulation.duplicate import duplicate_simulation
    from app.routes.simulation.export import export_simulations
    from app.routes.simulation.get import get_simulation
    from app.routes.simulation.search import search_simulation
    from app.routes.simulation.update import update_simulation

    return ComposedContextResponse(
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
        permission_docs=[
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
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
