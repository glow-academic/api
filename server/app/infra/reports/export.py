"""Reports export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_test_invocation_entries_internal — full dump
  3. search_test_invocation_groups — full dump
  4. search_test_invocation_runs — full dump
  5. Resource get tools — parallel hydration (names, departments, voices)
  6. ZIP generation (invocations.csv + groups.csv + runs.csv + brightspace.csv) + upload entry
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
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.entries.test_invocation_groups.search import (
    search_test_invocation_groups,
)
from app.tools.entries.test_invocation_runs.search import (
    search_test_invocation_runs,
)
from app.tools.resources.departments.get import get_departments
from app.tools.resources.names.get import get_names
from app.tools.resources.voices.get import get_voices

PIPE = "|"

INVOCATION_CSV_COLUMNS = [
    "invocation_id",
    "title",
    "position",
    "completed",
    "grade_score",
    "grade_passed",
    "grade_time_taken",
    "agents",
    "departments",
    "voice",
    "created_at",
]

GROUP_CSV_COLUMNS = [
    "id",
    "test_invocation_id",
    "agents",
    "voices",
    "prompts",
    "instructions",
    "tools",
    "created_at",
    "active",
]

RUN_CSV_COLUMNS = [
    "id",
    "test_invocation_id",
    "agents",
    "voices",
    "prompts",
    "instructions",
    "tools",
    "created_at",
    "active",
]

BRIGHTSPACE_CSV_COLUMNS = [
    "agent",
    "score",
    "passed",
    "time_taken",
]


class ExportReportsApiResponse(BaseModel):
    """Response model for reports export."""

    content: str
    file_name: str
    mime_type: str
    row_count: int


async def _empty_list() -> list:  # type: ignore[type-arg]
    return []


async def export_reports_impl(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
) -> ExportReportsApiResponse:
    """Reports full export using composable infra functions."""

    # -- Step 1: Profile context --
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search all test invocations (full dump) --
    async with pool.acquire() as conn:
        invocations, _total_count = await search_test_invocation_entries_internal(
            conn, limit=100000, offset=0
        )

    if not invocations:
        return ExportReportsApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 3: Search groups and runs --
    invocation_ids = [inv.invocation_id for inv in invocations]

    async def _fetch_groups() -> tuple[list, int]:
        async with pool.acquire() as conn:
            return await search_test_invocation_groups(
                conn, test_invocation_ids=invocation_ids, limit=100000, offset=0
            )

    async def _fetch_runs() -> tuple[list, int]:
        async with pool.acquire() as conn:
            return await search_test_invocation_runs(
                conn, test_invocation_ids=invocation_ids, limit=100000, offset=0
            )

    group_result, run_result = await asyncio.gather(
        _fetch_groups(),
        _fetch_runs(),
    )
    groups, _groups_total = group_result
    runs, _runs_total = run_result

    # -- Step 4: Parallel resource hydration --
    all_name_ids: set[UUID] = set()
    all_department_ids: set[UUID] = set()
    all_voice_ids: set[UUID] = set()

    for inv in invocations:
        all_name_ids.update(inv.agent_ids or [])
        all_department_ids.update(inv.department_ids or [])
        if inv.voice_id:
            all_voice_ids.add(inv.voice_id)

    for g in groups:
        all_name_ids.update(g.agent_ids or [])
        all_name_ids.update(g.prompt_ids or [])
        all_name_ids.update(g.instruction_ids or [])
        all_name_ids.update(g.tool_ids or [])
        all_voice_ids.update(g.voice_ids or [])

    for r in runs:
        all_name_ids.update(r.agent_ids or [])
        all_name_ids.update(r.prompt_ids or [])
        all_name_ids.update(r.instruction_ids or [])
        all_name_ids.update(r.tool_ids or [])
        all_voice_ids.update(r.voice_ids or [])

    async def _get_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, list(all_name_ids), redis)

    async def _get_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as conn:
            return await get_departments(conn, list(all_department_ids), redis)

    async def _get_voices() -> list:
        if not all_voice_ids:
            return []
        async with pool.acquire() as conn:
            return await get_voices(conn, list(all_voice_ids), redis)

    names_data, departments_data, voices_data = await asyncio.gather(
        _get_names(),
        _get_departments(),
        _get_voices(),
    )

    name_map: dict[UUID, str] = {n.id: n.name for n in names_data}
    department_map: dict[UUID, str] = {d.id: d.name or "" for d in departments_data}
    voice_map: dict[UUID, str] = {v.id: v.voice for v in voices_data}

    # -- Step 5: Generate CSVs --

    # invocations.csv
    inv_output = io.StringIO()
    inv_writer = csv.writer(inv_output)
    inv_writer.writerow(INVOCATION_CSV_COLUMNS)

    for inv in invocations:
        agents_str = PIPE.join(name_map.get(aid, "") for aid in (inv.agent_ids or []))
        departments_str = PIPE.join(
            department_map.get(did, "") for did in (inv.department_ids or [])
        )

        inv_writer.writerow(
            [
                str(inv.invocation_id),
                inv.invocation_title,
                str(inv.position),
                "Yes" if inv.invocation_completed else "No",
                str(inv.grade_score) if inv.grade_score is not None else "",
                "Yes" if inv.grade_passed else "No",
                str(inv.grade_time_taken) if inv.grade_time_taken is not None else "",
                agents_str,
                departments_str,
                voice_map.get(inv.voice_id, "") if inv.voice_id else "",
                str(inv.invocation_created_at),
            ]
        )

    # groups.csv
    grp_output = io.StringIO()
    grp_writer = csv.writer(grp_output)
    grp_writer.writerow(GROUP_CSV_COLUMNS)

    for g in groups:
        grp_writer.writerow(
            [
                str(g.id),
                str(g.test_invocation_id),
                PIPE.join(name_map.get(aid, "") for aid in (g.agent_ids or [])),
                PIPE.join(voice_map.get(vid, "") for vid in (g.voice_ids or [])),
                PIPE.join(name_map.get(pid, "") for pid in (g.prompt_ids or [])),
                PIPE.join(name_map.get(iid, "") for iid in (g.instruction_ids or [])),
                PIPE.join(name_map.get(tid, "") for tid in (g.tool_ids or [])),
                str(g.created_at),
                "Yes" if g.active else "No",
            ]
        )

    # runs.csv
    run_output = io.StringIO()
    run_writer = csv.writer(run_output)
    run_writer.writerow(RUN_CSV_COLUMNS)

    for r in runs:
        run_writer.writerow(
            [
                str(r.id),
                str(r.test_invocation_id),
                PIPE.join(name_map.get(aid, "") for aid in (r.agent_ids or [])),
                PIPE.join(voice_map.get(vid, "") for vid in (r.voice_ids or [])),
                PIPE.join(name_map.get(pid, "") for pid in (r.prompt_ids or [])),
                PIPE.join(name_map.get(iid, "") for iid in (r.instruction_ids or [])),
                PIPE.join(name_map.get(tid, "") for tid in (r.tool_ids or [])),
                str(r.created_at),
                "Yes" if r.active else "No",
            ]
        )

    # brightspace.csv — per-invocation agent grade summary
    bs_output = io.StringIO()
    bs_writer = csv.writer(bs_output)
    bs_writer.writerow(BRIGHTSPACE_CSV_COLUMNS)

    for inv in invocations:
        if inv.grade_score is not None:
            agent_name = PIPE.join(
                name_map.get(aid, "") for aid in (inv.agent_ids or [])
            )
            bs_writer.writerow(
                [
                    agent_name,
                    str(inv.grade_score),
                    "Yes" if inv.grade_passed else "No",
                    str(inv.grade_time_taken)
                    if inv.grade_time_taken is not None
                    else "",
                ]
            )

    # -- Step 6: Generate ZIP --
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("invocations.csv", inv_output.getvalue())
        zf.writestr("groups.csv", grp_output.getvalue())
        zf.writestr("runs.csv", run_output.getvalue())
        zf.writestr("brightspace.csv", bs_output.getvalue())

    zip_content = zip_buffer.getvalue()
    row_count = len(invocations) + len(groups) + len(runs)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"reports_export_{timestamp}.zip"

    return ExportReportsApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
