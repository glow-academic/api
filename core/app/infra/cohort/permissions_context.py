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

from app.infra.department_id_resolution import (
    resolve_department_ids_to_resource_ids,
)
from app.tools.artifacts.cohort.get import (
    get_cohorts as get_cohort_artifacts,
)
from app.tools.artifacts.profile.get import (
    get_profiles as get_profile_artifacts,
)
from app.tools.artifacts.simulation.get import (
    get_simulations as get_simulation_artifacts,
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
    from app.infra.cohort.types import (
        CohortFieldError,
        CreateCohortItem,
        UpdateCohortItem,
    )


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
    from app.infra.cohort.types import CohortFieldError

    errors: list[CohortFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    # --- Resolve denormalized flag booleans → canonical flag_ids entries ---

    denorm_flag_values: dict[str, bool] = {}
    if item.active is not None:
        denorm_flag_values["cohort_active"] = bool(item.active)
    if denorm_flag_values:
        all_flags = await search_flags(
            conn,
            redis,
            search=None,
            limit_count=200,
            bypass_cache=True,
        )
        resolved_flag_ids: list[UUID] = list(item.flag_ids or [])
        seen = set(resolved_flag_ids)
        for flag_type, desired_value in denorm_flag_values.items():
            match = next(
                (
                    f
                    for f in all_flags
                    if (
                        getattr(f, "type", None) == flag_type
                        or getattr(f, "name", None) == flag_type
                    )
                    and getattr(f, "value", None) is desired_value
                ),
                None,
            )
            if match and match.id and match.id not in seen:
                resolved_flag_ids.append(match.id)
                seen.add(match.id)
            elif not match:
                errors.append(
                    CohortFieldError(
                        field=flag_type,
                        message=(
                            f"Flag row not found for type={flag_type} "
                            f"value={desired_value}"
                        ),
                    )
                )
        item.flag_ids = resolved_flag_ids

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

    # --- Cross-artifact artifact ID → *_resource ID resolution ---
    #
    # ``simulation_ids`` / ``profile_ids`` supplied directly by the client are
    # *artifact* IDs (that is what ``/simulation/search`` and
    # ``/profile/search`` surface). ``cohort_simulations_junction`` and
    # ``cohort_profiles_junction`` are FK'd to ``simulations_resource`` /
    # ``profiles_resource`` (the denormalized snapshot each artifact owns via
    # its own self-junction), and the cohort read side hydrates them back
    # through the ``*_resource`` getters. Writing the artifact ID straight into
    # the junction violates the FK → HTTP 500. Resolve artifact IDs to their
    # snapshot resource IDs here; unknown IDs (e.g. an already-resolved
    # resource ID) pass through so the FK validates.
    #
    # Skip when the ``simulations`` / ``profiles`` CSV branch ran: those
    # already resolved via the resource search, yielding resource IDs.
    if item.simulations is None and item.simulation_ids:
        sim_artifacts = await get_simulation_artifacts(
            conn, list(item.simulation_ids), simulations=True
        )
        sim_map = {
            a.id: a.simulation_ids[0]
            for a in sim_artifacts
            if a.id and a.simulation_ids
        }
        item.simulation_ids = [
            sim_map.get(sid, sid) for sid in item.simulation_ids
        ]

    if item.profiles is None and item.profile_ids:
        profile_artifacts = await get_profile_artifacts(
            conn, list(item.profile_ids), profiles=True
        )
        profile_map = {
            a.id: a.profile_ids[0]
            for a in profile_artifacts
            if a.id and a.profile_ids
        }
        item.profile_ids = [
            profile_map.get(pid, pid) for pid in item.profile_ids
        ]

    # Resolve department *artifact* ids -> departments_resource ids before
    # the junction write. ``/department/search`` surfaces artifact ids, but
    # every ``*_departments_junction.departments_id`` is FK'd to
    # ``departments_resource``; writing a raw artifact id violates the FK
    # (HTTP 500). #282 class, missed for the cross-cutting ``department_ids``
    # dimension. Unknown/already-resolved ids pass through. No raw SQL.
    item.department_ids = await resolve_department_ids_to_resource_ids(
        conn, getattr(item, "department_ids", None)
    )

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
        return await get_names(pool, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        return await get_descriptions(pool, [description_id], redis, bypass_cache=True
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
