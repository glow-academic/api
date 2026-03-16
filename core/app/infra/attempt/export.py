"""Attempt export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_attempts — scoped to one attempt
  3. search_attempt_chats — scoped to one attempt
  4. search_attempt_messages — scoped to one attempt
  5. Resource get tools — parallel hydration (profiles, simulations, scenarios, personas)
  6. ZIP generation (attempts.csv + chats.csv + messages.csv) + upload entry creation
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
from app.tools.entries.attempt_message.search import search_attempt_messages
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

MESSAGE_CSV_COLUMNS = [
    "message_id",
    "chat_id",
    "attempt_id",
    "type",
    "created_at",
    "completed",
]


async def _empty() -> list:  # type: ignore[type-arg]
    return []


async def export_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    attempt_id: UUID,
) -> dict:
    """Attempt export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, department_ids
      2. search_attempts -> single attempt entry
      3. search_attempt_chats -> chats for the attempt
      4. search_attempt_messages -> messages for the attempt
      5. Parallel resource hydration -> human-readable values
      6. Generate ZIP (attempts.csv + chats.csv + messages.csv) and return base64-encoded content
    """
    from app.infra.attempt.types import ExportAttemptApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search attempt + chats + messages --

    async def _fetch_attempts() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_attempts(
                c, attempt_ids=[attempt_id], limit=1
            )
            return items

    async def _fetch_chats() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_attempt_chats(
                c, attempt_ids=[attempt_id], limit=100000
            )
            return items

    async def _fetch_messages() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_attempt_messages(
                c, attempt_ids=[attempt_id], limit=100000
            )
            return items

    attempts, chats, messages = await asyncio.gather(
        _fetch_attempts(),
        _fetch_chats(),
        _fetch_messages(),
    )

    if not attempts:
        return ExportAttemptApiResponse(
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

    for a in attempts:
        if a.profile_id:
            all_profile_ids.add(a.profile_id)
        if a.simulation_id:
            all_simulation_ids.add(a.simulation_id)
        if a.scenario_ids:
            all_scenario_ids.update(a.scenario_ids)
        if a.personas_id:
            all_persona_ids.add(a.personas_id)

    for c in chats:
        if c.scenario_id:
            all_scenario_ids.add(c.scenario_id)
        if c.persona_ids:
            all_persona_ids.update(c.persona_ids)

    async def _fetch_profiles() -> list:
        if not all_profile_ids:
            return []
        async with pool.acquire() as c:
            return await get_profiles(c, list(all_profile_ids), redis)

    async def _fetch_simulations() -> list:
        if not all_simulation_ids:
            return []
        async with pool.acquire() as c:
            return await get_simulations(c, list(all_simulation_ids), redis)

    async def _fetch_scenarios() -> list:
        if not all_scenario_ids:
            return []
        async with pool.acquire() as c:
            return await get_scenarios(c, list(all_scenario_ids), redis)

    async def _fetch_personas() -> list:
        if not all_persona_ids:
            return []
        async with pool.acquire() as c:
            return await get_personas(c, list(all_persona_ids), redis)

    (
        profiles_data,
        simulations_data,
        scenarios_data,
        personas_data,
    ) = await asyncio.gather(
        _fetch_profiles(),
        _fetch_simulations(),
        _fetch_scenarios(),
        _fetch_personas(),
    )

    # Build lookup maps
    profile_map = {p.id: p.name or "" for p in profiles_data}
    simulation_map = {s.id: s.name or "" for s in simulations_data}
    scenario_map = {s.id: s.name or "" for s in scenarios_data}
    persona_map = {p.id: p.name or "" for p in personas_data}

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
                "",  # cohort — not hydrated for attempt export
                "",  # department — not hydrated for attempt export
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

    # messages.csv
    messages_output = io.StringIO()
    messages_writer = csv.writer(messages_output)
    messages_writer.writerow(MESSAGE_CSV_COLUMNS)

    for m in messages:
        messages_writer.writerow(
            [
                str(m.message_id),
                str(m.chat_id) if m.chat_id else "",
                str(m.attempt_id) if m.attempt_id else "",
                m.type or "",
                str(m.created_at) if m.created_at else "",
                "Yes" if m.completed else "No",
            ]
        )

    # -- Step 5: Generate ZIP + upload --

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("attempts.csv", attempts_output.getvalue())
        zf.writestr("chats.csv", chats_output.getvalue())
        zf.writestr("messages.csv", messages_output.getvalue())

    zip_content = zip_buffer.getvalue()
    row_count = len(attempts) + len(chats) + len(messages)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"attempt_export_{timestamp}.zip"

    return ExportAttemptApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
