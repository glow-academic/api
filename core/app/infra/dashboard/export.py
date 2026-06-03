"""Dashboard export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_attempts — full dump (all entries, no filters, no pagination)
  3. search_chat_entries_internal — full dump of chat entries
  4. Resource get tools — parallel hydration (profiles, simulations, scenarios, etc.)
  5. ZIP generation (attempts.csv + chats.csv) + upload entry creation
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import zipfile
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.dashboard.visibility import resolve_visible_profile_ids
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.chat.search import search_chat_entries_internal
from app.tools.resources.cohorts.get import get_cohorts
from app.tools.resources.departments.get import get_departments
from app.tools.resources.personas.get import get_personas
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.simulations.get import get_simulations

PIPE = "|"

ATTEMPT_CSV_COLUMNS = [
    "attempt_id",
    "attempt_date",
    "profile",
    "simulation",
    "scenarios",
    "persona",
    "cohort",
    "department",
    "practice",
    "infinite_mode",
    "num_chats",
    "archived",
]

CHAT_CSV_COLUMNS = [
    "chat_entry_id",
    "parent_id",
    "scenario",
    "name",
    "description",
    "departments",
    "personas",
    "created_at",
    "active",
]


async def export_dashboard_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
) -> dict:
    """Dashboard full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_attempts → all entries (full dump, no pagination)
      3. search_chat_entries_internal → all chat entries (full dump)
      4. Parallel resource hydration → human-readable values
      5. Generate ZIP (attempts.csv + chats.csv) + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.dashboard.types import ExportDashboardApiResponse

    # -- Step 1: Profile context --

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # Authorization: scope the attempt dump to the profiles the actor may see,
    # mirroring the on-screen sibling ``dashboard/get.py`` (~101-125). Without
    # this, any holder of ``attempt:export`` could dump every attempt+grade+
    # profile across all departments (IDOR / mass exposure, #152).
    # ``resolve_visible_profile_ids`` already encodes the full policy (self +
    # same-department lower-privilege, or the entire org for role_level 0).
    with timed("visibility"):
        visible_profile_ids = await resolve_visible_profile_ids(pool, profile)

    # -- Step 2: Search attempts (scoped to visible profiles) --

    with timed("query_attempts"):
     async with pool.acquire() as conn:
        attempts, _total_count = await search_attempts(
            conn,
            redis, profile_ids=visible_profile_ids,
            limit=100000,
            offset=0,
        )

    # -- Step 3: Search all chat entries (full dump) --

    with timed("query_chats"):
     async with pool.acquire() as conn:
        chats = await search_chat_entries_internal(
            conn,
            redis, limit_count=100000,
            offset_count=0,
        )

    if not attempts and not chats:
        return ExportDashboardApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 4: Parallel resource hydration --

    # Collect all resource IDs from attempts
    all_profile_ids: set[UUID] = set()
    all_simulation_ids: set[UUID] = set()
    all_scenario_ids: set[UUID] = set()
    all_persona_ids: set[UUID] = set()
    all_cohort_ids: set[UUID] = set()
    all_department_ids: set[UUID] = set()

    for a in attempts:
        if a.profile_id:
            all_profile_ids.add(a.profile_id)
        if a.simulation_id:
            all_simulation_ids.add(a.simulation_id)
        if a.scenario_ids:
            all_scenario_ids.update(a.scenario_ids)
        if a.personas_id:
            all_persona_ids.add(a.personas_id)
        if a.cohort_id:
            all_cohort_ids.add(a.cohort_id)
        if a.department_id:
            all_department_ids.add(a.department_id)

    # Collect resource IDs from chats
    for c in chats:
        if c.get("scenario_id"):
            all_scenario_ids.add(c["scenario_id"])
        if c.get("persona_ids"):
            all_persona_ids.update(c["persona_ids"])
        if c.get("department_ids"):
            all_department_ids.update(c["department_ids"])

    async def _get_profiles() -> list:
        if not all_profile_ids:
            return []
        return await get_profiles(pool, list(all_profile_ids), redis)

    async def _get_simulations() -> list:
        if not all_simulation_ids:
            return []
        return await get_simulations(pool, list(all_simulation_ids), redis)

    async def _get_scenarios() -> list:
        if not all_scenario_ids:
            return []
        return await get_scenarios(pool, list(all_scenario_ids), redis)

    async def _get_personas() -> list:
        if not all_persona_ids:
            return []
        return await get_personas(pool, list(all_persona_ids), redis)

    async def _get_cohorts() -> list:
        if not all_cohort_ids:
            return []
        return await get_cohorts(pool, list(all_cohort_ids), redis)

    async def _get_departments() -> list:
        if not all_department_ids:
            return []
        return await get_departments(pool, list(all_department_ids), redis)

    with timed("hydrate"):
     (
        profiles_data,
        simulations_data,
        scenarios_data,
        personas_data,
        cohorts_data,
        departments_data,
     ) = await asyncio.gather(
        _get_profiles(),
        _get_simulations(),
        _get_scenarios(),
        _get_personas(),
        _get_cohorts(),
        _get_departments(),
    )

    # Build lookup maps
    profile_map = {p.id: p.name or "" for p in profiles_data}
    simulation_map = {s.id: s.name or "" for s in simulations_data}
    scenario_map = {s.id: s.name or "" for s in scenarios_data}
    persona_map = {p.id: p.name or "" for p in personas_data}
    cohort_map = {c.id: c.name or "" for c in cohorts_data}
    department_map = {d.id: d.name or "" for d in departments_data}

    # -- Step 5: Generate ZIP (attempts.csv + chats.csv) + upload --

    # Generate attempts CSV
    attempts_output = io.StringIO()
    attempts_writer = csv.writer(attempts_output)
    attempts_writer.writerow(ATTEMPT_CSV_COLUMNS)

    for a in attempts:
        scenarios_str = PIPE.join(
            scenario_map.get(sid, "") for sid in (a.scenario_ids or [])
        )

        attempts_writer.writerow(
            [
                str(a.attempt_id),
                str(a.attempt_created_at),
                profile_map.get(a.profile_id, "") if a.profile_id else "",
                simulation_map.get(a.simulation_id, "") if a.simulation_id else "",
                scenarios_str,
                persona_map.get(a.personas_id, "") if a.personas_id else "",
                cohort_map.get(a.cohort_id, "") if a.cohort_id else "",
                department_map.get(a.department_id, "") if a.department_id else "",
                "Yes" if a.practice else "No",
                "Yes" if a.infinite_mode else "No",
                str(a.num_chats),
                "Yes" if a.is_archived else "No",
            ]
        )

    # Generate chats CSV
    chats_output = io.StringIO()
    chats_writer = csv.writer(chats_output)
    chats_writer.writerow(CHAT_CSV_COLUMNS)

    for c in chats:
        departments_str = PIPE.join(
            department_map.get(did, "") for did in (c.get("department_ids") or [])
        )
        personas_str = PIPE.join(
            persona_map.get(pid, "") for pid in (c.get("persona_ids") or [])
        )

        chats_writer.writerow(
            [
                str(c.get("chat_entry_id", "")),
                str(c.get("parent_id", "")),
                scenario_map.get(c.get("scenario_id"), "")
                if c.get("scenario_id")
                else "",
                c.get("name", ""),
                c.get("description", ""),
                departments_str,
                personas_str,
                str(c.get("created_at", "")),
                "Yes" if c.get("active") else "No",
            ]
        )

    # Create ZIP
    with timed("zip_build"):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("attempts.csv", attempts_output.getvalue())
            zf.writestr("chats.csv", chats_output.getvalue())

        zip_content = zip_buffer.getvalue()
    row_count = len(attempts) + len(chats)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"dashboard_export_{timestamp}.zip"

    return ExportDashboardApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
