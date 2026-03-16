"""Simulation export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_simulations — full dump (all IDs, no filters, no pagination)
  3. get_simulations — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, scenarios, etc.)
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
from app.tools.artifacts.simulation.get import get_simulations
from app.tools.artifacts.simulation.search import search_simulations
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.scenario_positions.get import get_scenario_positions
from app.tools.resources.scenario_time_limits.get import (
    get_scenario_time_limits,
)
from app.tools.resources.scenarios.get import (
    get_scenarios as get_scenarios_resource,
)

PIPE = "|"

CSV_COLUMNS = [
    "simulation_id",
    "name",
    "description",
    "active",
    "departments",
    "scenarios",
    "scenario_positions",
    "scenario_time_limits",
]


async def export_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    simulation_id: UUID | None = None,
) -> dict:
    """Simulation full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, department_ids
      2. search_simulations -> all IDs (full dump, no pagination)
      3. get_simulations -> junction IDs per artifact
      4. Parallel resource hydration -> human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.simulation.types import ExportSimulationApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search all simulations (full dump) --

    if simulation_id:
        simulation_ids = [simulation_id]
    else:
        async with pool.acquire() as conn:
            simulation_ids, _total_count = await search_simulations(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not simulation_ids:
            return ExportSimulationApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # -- Step 3: Get simulation artifacts with all junction IDs --

    async with pool.acquire() as conn:
        artifacts = await get_simulations(
            conn,
            simulation_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            scenarios=True,
            scenario_flags=True,
            scenario_positions=True,
            scenario_rubrics=True,
            scenario_time_limits=True,
        )

    # -- Step 4: Parallel resource hydration --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_scenario_ids: list[UUID] = []
    all_scenario_position_ids: list[UUID] = []
    all_scenario_time_limit_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_scenario_ids.extend(a.scenario_ids or [])
        all_scenario_position_ids.extend(a.scenario_position_ids or [])
        all_scenario_time_limit_ids.extend(a.scenario_time_limit_ids or [])

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

    async def _fetch_scenarios() -> list:
        if not all_scenario_ids:
            return []
        async with pool.acquire() as conn:
            return await get_scenarios_resource(conn, all_scenario_ids, redis)

    async def _fetch_scenario_positions() -> list:
        if not all_scenario_position_ids:
            return []
        async with pool.acquire() as conn:
            return await get_scenario_positions(conn, all_scenario_position_ids, redis)

    async def _fetch_scenario_time_limits() -> list:
        if not all_scenario_time_limit_ids:
            return []
        async with pool.acquire() as conn:
            return await get_scenario_time_limits(
                conn, all_scenario_time_limit_ids, redis
            )

    (
        names_data,
        descriptions_data,
        departments_data,
        scenarios_data,
        scenario_positions_data,
        scenario_time_limits_data,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_departments(),
        _fetch_scenarios(),
        _fetch_scenario_positions(),
        _fetch_scenario_time_limits(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    scenario_map = {s.id: s.name for s in scenarios_data}
    scenario_position_map = {
        sp.id: f"{scenario_map.get(sp.scenario_id, '')}:{sp.value}"
        for sp in scenario_positions_data
    }
    scenario_time_limit_map = {
        stl.id: f"{scenario_map.get(stl.scenario_id, '')}:{stl.time_limit_seconds}"
        for stl in scenario_time_limits_data
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
        scenarios_str = PIPE.join(
            scenario_map.get(sid, "") for sid in (a.scenario_ids or [])
        )
        scenario_positions_str = PIPE.join(
            scenario_position_map.get(spid, "")
            for spid in (a.scenario_position_ids or [])
        )
        scenario_time_limits_str = PIPE.join(
            scenario_time_limit_map.get(stlid, "")
            for stlid in (a.scenario_time_limit_ids or [])
        )

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                scenarios_str,
                scenario_positions_str,
                scenario_time_limits_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"simulations_export_{timestamp}.csv"

    return ExportSimulationApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
