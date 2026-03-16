"""Cohort export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_cohorts — full dump (all IDs, no filters, no pagination)
  3. get_cohorts — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, departments, etc.)
  5. CSV generation + upload entry creation
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.cohort.get import get_cohorts
from app.tools.artifacts.cohort.search import search_cohorts
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.profile_personas.get import get_profile_personas
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.simulation_availability.get import (
    get_simulation_availability,
)
from app.tools.resources.simulation_positions.get import (
    get_simulation_positions,
)
from app.tools.resources.simulations.get import get_simulations

PIPE = "|"

CSV_COLUMNS = [
    "cohort_id",
    "name",
    "description",
    "active",
    "departments",
    "simulations",
    "simulation_positions",
    "simulation_availability",
    "profiles",
    "profile_personas",
]


async def export_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    cohort_id: UUID | None = None,
) -> dict:
    """Cohort full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, department_ids
      2. search_cohorts -> all IDs (full dump, no pagination)
      3. get_cohorts -> junction IDs per artifact
      4. Parallel resource hydration -> human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.cohort.types import ExportCohortApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search all cohorts (full dump) --

    if cohort_id:
        cohort_ids = [cohort_id]
    else:
        async with pool.acquire() as conn:
            cohort_ids, _total_count = await search_cohorts(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not cohort_ids:
            return ExportCohortApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # -- Step 3: Get cohort artifacts with all junction IDs --

    async with pool.acquire() as conn:
        artifacts = await get_cohorts(
            conn,
            cohort_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            profiles=True,
            profile_personas=True,
            simulations=True,
            simulation_availability=True,
            simulation_positions=True,
        )

    # -- Step 4: Parallel resource hydration --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_simulation_ids: list[UUID] = []
    all_simulation_position_ids: list[UUID] = []
    all_simulation_availability_ids: list[UUID] = []
    all_profile_ids: list[UUID] = []
    all_profile_persona_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_simulation_ids.extend(a.simulation_ids or [])
        all_simulation_position_ids.extend(a.simulation_position_ids or [])
        all_simulation_availability_ids.extend(a.simulation_availability_ids or [])
        all_profile_ids.extend(a.profiles_ids or [])
        all_profile_persona_ids.extend(a.profile_persona_ids or [])

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _fetch_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as conn:
            return await get_departments(conn, all_department_ids, redis)

    async def _fetch_simulations() -> list:
        if not all_simulation_ids:
            return []
        async with pool.acquire() as conn:
            return await get_simulations(conn, all_simulation_ids, redis)

    async def _fetch_simulation_positions() -> list:
        if not all_simulation_position_ids:
            return []
        async with pool.acquire() as conn:
            return await get_simulation_positions(
                conn, all_simulation_position_ids, redis
            )

    async def _fetch_simulation_availability() -> list:
        if not all_simulation_availability_ids:
            return []
        async with pool.acquire() as conn:
            return await get_simulation_availability(
                conn, all_simulation_availability_ids, redis
            )

    async def _fetch_profiles() -> list:
        if not all_profile_ids:
            return []
        async with pool.acquire() as conn:
            return await get_profiles(conn, all_profile_ids, redis)

    async def _fetch_profile_personas() -> list:
        if not all_profile_persona_ids:
            return []
        async with pool.acquire() as conn:
            return await get_profile_personas(conn, all_profile_persona_ids, redis)

    (
        names_data,
        descriptions_data,
        departments_data,
        simulations_data,
        simulation_positions_data,
        simulation_availability_data,
        profiles_data,
        profile_personas_data,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_departments(),
        _fetch_simulations(),
        _fetch_simulation_positions(),
        _fetch_simulation_availability(),
        _fetch_profiles(),
        _fetch_profile_personas(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    simulation_map = {s.id: s.name for s in simulations_data}
    simulation_position_map = {sp.id: str(sp.value) for sp in simulation_positions_data}
    simulation_availability_map = {
        sa.id: f"{sa.type}:{sa.time.isoformat()}" if sa.time else sa.type
        for sa in simulation_availability_data
    }
    profile_map = {p.id: p.name for p in profiles_data}
    profile_persona_map = {
        pp.id: f"{pp.profile_id}:{pp.persona_id}" for pp in profile_personas_data
    }

    # -- Step 5: Generate CSV + upload --

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)

    for a in artifacts:
        # Single-select: first resource value
        name = name_map.get(a.name_ids[0], "") if a.name_ids else ""
        description = (
            description_map.get(a.description_ids[0], "") if a.description_ids else ""
        )

        # Active flag
        active = "Yes" if a.active else "No"

        # Multi-select: pipe-delimited values
        departments_str = PIPE.join(
            department_map.get(did, "") for did in (a.department_ids or [])
        )
        simulations_str = PIPE.join(
            simulation_map.get(sid, "") for sid in (a.simulation_ids or [])
        )
        simulation_positions_str = PIPE.join(
            simulation_position_map.get(spid, "")
            for spid in (a.simulation_position_ids or [])
        )
        simulation_availability_str = PIPE.join(
            simulation_availability_map.get(said, "")
            for said in (a.simulation_availability_ids or [])
        )
        profiles_str = PIPE.join(
            profile_map.get(pid, "") for pid in (a.profiles_ids or [])
        )
        profile_personas_str = PIPE.join(
            profile_persona_map.get(ppid, "") for ppid in (a.profile_persona_ids or [])
        )

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                simulations_str,
                simulation_positions_str,
                simulation_availability_str,
                profiles_str,
                profile_personas_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"cohorts_export_{timestamp}.csv"

    return ExportCohortApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
