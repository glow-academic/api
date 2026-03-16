"""Activity export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search tools — full dump of activity, logins, problems, grants, emulations
  3. Resource get tools — parallel hydration (profiles)
  4. ZIP generation (activity.csv + logins.csv + problems.csv + grants.csv + emulations.csv) + upload entry creation
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

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.activity.search import search_activity
from app.tools.entries.emulations.search import search_emulations
from app.tools.entries.grants.search import search_grants
from app.tools.entries.logins.search import search_logins
from app.tools.entries.problems.search import search_problems
from app.tools.resources.profiles.get import get_profiles

PIPE = "|"

ACTIVITY_CSV_COLUMNS = [
    "id",
    "profile",
    "session_id",
    "created_at",
    "active",
    "mcp",
    "generated",
]

LOGINS_CSV_COLUMNS = [
    "id",
    "profile",
    "session_id",
    "created_at",
    "active",
    "mcp",
    "generated",
]

PROBLEMS_CSV_COLUMNS = [
    "id",
    "profile",
    "session_id",
    "type",
    "message",
    "resolved",
    "created_at",
    "active",
    "mcp",
    "generated",
]

GRANTS_CSV_COLUMNS = [
    "id",
    "session_id",
    "expires_at",
    "created_at",
    "active",
    "generated",
    "mcp",
]

EMULATIONS_CSV_COLUMNS = [
    "id",
    "profile",
    "grant_id",
    "session_id",
    "created_at",
    "active",
    "mcp",
    "generated",
]


async def export_activity_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
) -> dict:
    """Activity full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Parallel search all entry types (full dump, no pagination)
      3. Parallel resource hydration → human-readable values
      4. Generate ZIP (activity.csv + logins.csv + problems.csv + grants.csv + emulations.csv) + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.activity.types import ExportActivityApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel search all entry types (full dump) --

    async def _fetch_activity() -> list:
        async with pool.acquire() as c:
            return await search_activity(c, limit=100000, offset=0)

    async def _fetch_logins() -> list:
        async with pool.acquire() as c:
            return await search_logins(c, limit=100000, offset=0)

    async def _fetch_problems() -> list:
        async with pool.acquire() as c:
            return await search_problems(c, limit=100000, offset=0)

    async def _fetch_grants() -> list:
        async with pool.acquire() as c:
            return await search_grants(c, limit=100000, offset=0)

    async def _fetch_emulations() -> list:
        async with pool.acquire() as c:
            return await search_emulations(c, limit=100000, offset=0)

    (
        activity_entries,
        logins_entries,
        problems_entries,
        grants_entries,
        emulations_entries,
    ) = await asyncio.gather(
        _fetch_activity(),
        _fetch_logins(),
        _fetch_problems(),
        _fetch_grants(),
        _fetch_emulations(),
    )

    if (
        not activity_entries
        and not logins_entries
        and not problems_entries
        and not grants_entries
        and not emulations_entries
    ):
        return ExportActivityApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 3: Parallel resource hydration --

    # Collect all profile IDs from entries that have profile_id
    all_profile_ids: set[UUID] = set()

    for a in activity_entries:
        if a.profile_id:
            all_profile_ids.add(a.profile_id)

    for lg in logins_entries:
        if lg.profile_id:
            all_profile_ids.add(lg.profile_id)

    for p in problems_entries:
        if p.profile_id:
            all_profile_ids.add(p.profile_id)

    for e in emulations_entries:
        if e.profile_id:
            all_profile_ids.add(e.profile_id)

    async def _fetch_profiles() -> list:
        if not all_profile_ids:
            return []
        async with pool.acquire() as c:
            return await get_profiles(c, list(all_profile_ids), redis)

    (profiles_data,) = await asyncio.gather(
        _fetch_profiles(),
    )

    # Build lookup maps
    profile_map = {p.id: p.name or "" for p in profiles_data}

    # -- Step 4: Generate ZIP + upload --

    # Generate activity CSV
    activity_output = io.StringIO()
    activity_writer = csv.writer(activity_output)
    activity_writer.writerow(ACTIVITY_CSV_COLUMNS)

    for a in activity_entries:
        activity_writer.writerow(
            [
                str(a.id),
                profile_map.get(a.profile_id, "") if a.profile_id else "",
                str(a.session_id) if a.session_id else "",
                str(a.created_at),
                "Yes" if a.active else "No",
                "Yes" if a.mcp else "No",
                "Yes" if a.generated else "No",
            ]
        )

    # Generate logins CSV
    logins_output = io.StringIO()
    logins_writer = csv.writer(logins_output)
    logins_writer.writerow(LOGINS_CSV_COLUMNS)

    for lg in logins_entries:
        logins_writer.writerow(
            [
                str(lg.id),
                profile_map.get(lg.profile_id, "") if lg.profile_id else "",
                str(lg.session_id) if lg.session_id else "",
                str(lg.created_at),
                "Yes" if lg.active else "No",
                "Yes" if lg.mcp else "No",
                "Yes" if lg.generated else "No",
            ]
        )

    # Generate problems CSV
    problems_output = io.StringIO()
    problems_writer = csv.writer(problems_output)
    problems_writer.writerow(PROBLEMS_CSV_COLUMNS)

    for p in problems_entries:
        problems_writer.writerow(
            [
                str(p.id),
                profile_map.get(p.profile_id, "") if p.profile_id else "",
                str(p.session_id),
                p.type,
                p.message,
                "Yes" if p.resolved else "No",
                str(p.created_at),
                "Yes" if p.active else "No",
                "Yes" if p.mcp else "No",
                "Yes" if p.generated else "No",
            ]
        )

    # Generate grants CSV
    grants_output = io.StringIO()
    grants_writer = csv.writer(grants_output)
    grants_writer.writerow(GRANTS_CSV_COLUMNS)

    for g in grants_entries:
        grants_writer.writerow(
            [
                str(g.id),
                str(g.session_id),
                str(g.expires_at),
                str(g.created_at),
                "Yes" if g.active else "No",
                "Yes" if g.generated else "No",
                "Yes" if g.mcp else "No",
            ]
        )

    # Generate emulations CSV
    emulations_output = io.StringIO()
    emulations_writer = csv.writer(emulations_output)
    emulations_writer.writerow(EMULATIONS_CSV_COLUMNS)

    for e in emulations_entries:
        emulations_writer.writerow(
            [
                str(e.id),
                profile_map.get(e.profile_id, "") if e.profile_id else "",
                str(e.grant_id),
                str(e.session_id),
                str(e.created_at),
                "Yes" if e.active else "No",
                "Yes" if e.mcp else "No",
                "Yes" if e.generated else "No",
            ]
        )

    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("activity.csv", activity_output.getvalue())
        zf.writestr("logins.csv", logins_output.getvalue())
        zf.writestr("problems.csv", problems_output.getvalue())
        zf.writestr("grants.csv", grants_output.getvalue())
        zf.writestr("emulations.csv", emulations_output.getvalue())

    zip_content = zip_buffer.getvalue()
    row_count = (
        len(activity_entries)
        + len(logins_entries)
        + len(problems_entries)
        + len(grants_entries)
        + len(emulations_entries)
    )

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"activity_export_{timestamp}.zip"

    return ExportActivityApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
