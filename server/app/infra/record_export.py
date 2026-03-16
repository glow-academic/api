"""Record export logic — composable infra architecture.

Like dashboard_export but scoped to a single profile (target_profile_id).

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_attempts — scoped to target_profile_id
  3. search_attempt_chats — scoped to target_profile_id
  4. Resource get tools — parallel hydration (profiles, simulations, scenarios, personas, cohorts, departments)
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
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_chat.search import search_attempt_chats
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
    "chat_id",
    "attempt_id",
    "scenario",
    "persona",
    "rubric_id",
    "grade_score",
    "grade_total_points",
    "grade_passed",
    "completed",
    "chat_created_at",
]


async def _empty() -> list:  # type: ignore[type-arg]
    return []


async def export_record_client(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    target_profile_id: UUID,
) -> dict:
    """Record export using composable infra functions.

    Like dashboard export but scoped to a single profile.

    Flow:
      1. resolve_profile_identity_context -> role, department_ids
      2. search_attempts -> all attempts for target_profile_id
      3. search_attempt_chats -> all chats for target_profile_id
      4. Parallel resource hydration -> human-readable values
      5. Generate ZIP (attempts.csv + chats.csv) + create upload entry
    """
    from app.infra.record.types import ExportRecordApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search attempts + chats scoped to target profile --

    async def _fetch_attempts() -> list:
        async with pool.acquire() as conn:
            attempts, _total_count = await search_attempts(
                conn, profile_ids=[target_profile_id], limit=100000, offset=0
            )
            return attempts

    async def _fetch_chats() -> list:
        async with pool.acquire() as conn:
            chats, _total_count = await search_attempt_chats(
                conn, profile_ids=[target_profile_id], limit=100000, offset=0
            )
            return chats

    attempts, chats = await asyncio.gather(
        _fetch_attempts(),
        _fetch_chats(),
    )

    if not attempts and not chats:
        return ExportRecordApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 3: Parallel resource hydration --

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

    for c in chats:
        if c.scenario_id:
            all_scenario_ids.add(c.scenario_id)
        if c.persona_ids:
            all_persona_ids.update(c.persona_ids)

    async def _get_profiles() -> list:
        if not all_profile_ids:
            return []
        async with pool.acquire() as conn:
            return await get_profiles(conn, list(all_profile_ids), redis)

    async def _get_simulations() -> list:
        if not all_simulation_ids:
            return []
        async with pool.acquire() as conn:
            return await get_simulations(conn, list(all_simulation_ids), redis)

    async def _get_scenarios() -> list:
        if not all_scenario_ids:
            return []
        async with pool.acquire() as conn:
            return await get_scenarios(conn, list(all_scenario_ids), redis)

    async def _get_personas() -> list:
        if not all_persona_ids:
            return []
        async with pool.acquire() as conn:
            return await get_personas(conn, list(all_persona_ids), redis)

    async def _get_cohorts() -> list:
        if not all_cohort_ids:
            return []
        async with pool.acquire() as conn:
            return await get_cohorts(conn, list(all_cohort_ids), redis)

    async def _get_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as conn:
            return await get_departments(conn, list(all_department_ids), redis)

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

    # -- Step 4: Generate CSVs --

    # attempts.csv
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

    # chats.csv
    chats_output = io.StringIO()
    chats_writer = csv.writer(chats_output)
    chats_writer.writerow(CHAT_CSV_COLUMNS)

    for c in chats:
        personas_str = PIPE.join(
            persona_map.get(pid, "") for pid in (c.persona_ids or [])
        )

        chats_writer.writerow(
            [
                str(c.chat_id),
                str(c.attempt_id),
                scenario_map.get(c.scenario_id, "") if c.scenario_id else "",
                personas_str,
                str(c.rubric_id) if c.rubric_id else "",
                str(c.grade_score) if c.grade_score is not None else "",
                str(c.grade_total_points) if c.grade_total_points is not None else "",
                "Yes" if c.grade_passed else "No",
                "Yes" if c.completed else "No",
                str(c.chat_created_at) if c.chat_created_at else "",
            ]
        )

    # -- Step 5: Generate ZIP + upload --

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("attempts.csv", attempts_output.getvalue())
        zf.writestr("chats.csv", chats_output.getvalue())

    zip_content = zip_buffer.getvalue()
    row_count = len(attempts) + len(chats)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"record_export_{timestamp}.zip"

    return ExportRecordApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
