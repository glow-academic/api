"""Cohort permissions context + shared save helpers.

Permissions context:
  1. resolve_cohort_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_cohort_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → cohorts_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.cohort.get import (
    get_cohorts as get_cohort_artifacts,
)
from app.tools.resources.cohorts.create import (
    create_cohort as create_cohort_resource,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.profiles.search import search_profiles
from app.tools.resources.simulations.search import search_simulations

if TYPE_CHECKING:
    from app.infra.cohort.create import CohortFieldError, CreateCohortItem
    from app.infra.cohort.types import UpdateCohortItem


@dataclass(frozen=True)
class CohortPermissionsContext:
    """Lightweight context for cohort permission checks."""

    exists: bool
    department_ids: list[UUID]


async def resolve_cohort_permissions_context(
    conn: asyncpg.Connection,
    cohort_id: UUID,
) -> CohortPermissionsContext:
    """Fetch just what's needed for cohort permission checks.

    Single black-box tool call:
      1. get_cohort_artifacts → department_ids
    """
    artifacts = await get_cohort_artifacts(
        conn,
        [cohort_id],
        departments=True,
    )

    if not artifacts:
        return CohortPermissionsContext(
            exists=False,
            department_ids=[],
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])

    return CohortPermissionsContext(
        exists=True,
        department_ids=department_ids,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both cohort_create and cohort_update
# ---------------------------------------------------------------------------


async def resolve_cohort_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateCohortItem | UpdateCohortItem,
    is_create: bool,
) -> list[CohortFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.
    For 'match' resources (departments, simulations, profiles, flags):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.cohort.create import CohortFieldError

    errors: list[CohortFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    # --- Match resources ---

    if item.is_inactive is not None and item.flag_id is None:
        results = await search_flags(
            conn,
            redis,
            search=None,
            flag_type="cohort_active",
            limit_count=1000,
        )
        match = next((f for f in results if f.type == "cohort_active"), None)
        if match and match.id:
            if not item.is_inactive:
                # Active → set the cohort_active flag
                item.flag_id = match.id
            # Inactive → leave flag_id as None (no flag)
        elif not item.is_inactive:
            errors.append(
                CohortFieldError(
                    field="is_inactive", message="Active flag resource not found"
                )
            )

    if item.departments is not None and item.department_ids is None:
        all_depts = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        dept_name_map = {d.name.lower(): d.id for d in all_depts if d.name and d.id}
        resolved_ids = []
        for dept_name in item.departments:
            dept_id = dept_name_map.get(dept_name.lower())
            if dept_id:
                resolved_ids.append(dept_id)
            else:
                errors.append(
                    CohortFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    if item.simulations is not None and item.simulation_ids is None:
        all_simulations = await search_simulations(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        sim_name_map = {
            s.name.lower(): s.id for s in all_simulations if s.name and s.id
        }
        resolved_ids = []
        for sim_name in item.simulations:
            sid = sim_name_map.get(sim_name.lower())
            if sid:
                resolved_ids.append(sid)
            else:
                errors.append(
                    CohortFieldError(
                        field="simulations",
                        message=f'Simulation "{sim_name}" not found',
                    )
                )
        if not any(e.field == "simulations" for e in errors):
            item.simulation_ids = resolved_ids

    if item.profiles is not None and item.profile_ids is None:
        all_profiles = await search_profiles(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        profile_name_map = {
            p.name.lower(): p.id for p in all_profiles if p.name and p.id
        }
        resolved_ids = []
        for profile_name in item.profiles:
            pid = profile_name_map.get(profile_name.lower())
            if pid:
                resolved_ids.append(pid)
            else:
                errors.append(
                    CohortFieldError(
                        field="profiles",
                        message=f'Profile "{profile_name}" not found',
                    )
                )
        if not any(e.field == "profiles" for e in errors):
            item.profile_ids = resolved_ids

    # --- Validate required fields ---

    if item.name_id is None:
        errors.append(CohortFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    department_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    profile_persona_ids: list[UUID] | None = None,
    simulation_position_ids: list[UUID] | None = None,
    simulation_availability_ids: list[UUID] | None = None,
) -> UUID:
    """Create a cohorts_resource snapshot by hydrating IDs to values.

    Each parallel branch acquires its own connection from the pool.
    """

    async def _get_names() -> list:
        if not name_id:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, [description_id], redis, bypass_cache=True
            )

    names, descriptions = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
    )

    async with pool.acquire() as conn:
        result = await create_cohort_resource(
            conn,
            redis,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            department_ids=department_ids,
            simulation_ids=simulation_ids,
            profile_ids=profile_ids,
            profile_persona_ids=profile_persona_ids,
            simulation_position_ids=simulation_position_ids,
            simulation_availability_ids=simulation_availability_ids,
        )
    return result.id
