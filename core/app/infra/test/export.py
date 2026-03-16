"""Test export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_tests — test metadata for given test_id
  3. search_test_invocation_entries_internal — invocations for this test
  4. search_test_invocation_runs — runs for these invocations
  5. Resource get tools — parallel hydration (departments, names)
  6. ZIP generation (tests.csv + invocations.csv + runs.csv) + upload entry creation
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
from app.infra.test.types import ExportTestApiResponse
from app.tools.entries.test.search import search_tests
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.entries.test_invocation_runs.search import (
    search_test_invocation_runs,
)
from app.tools.resources.departments.get import get_departments
from app.tools.resources.names.get import get_names
from app.tools.resources.voices.get import get_voices

PIPE = "|"

TEST_CSV_COLUMNS = [
    "test_id",
    "eval_id",
    "profile_id",
    "departments",
    "test_name",
    "test_description",
    "num_invocations",
    "infinite_mode",
    "is_dynamic",
    "archived",
    "test_created_at",
]

INVOCATION_CSV_COLUMNS = [
    "invocation_id",
    "test_id",
    "group_id",
    "invocation_created_at",
    "invocation_title",
    "use_custom",
    "position",
    "invocation_completed",
    "grade_id",
    "grade_score",
    "grade_passed",
    "grade_time_taken",
    "rubric_id",
    "agents",
    "quality_id",
    "departments",
    "voice",
    "temperature_level_id",
    "reasoning_level_id",
    "modality_ids",
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


async def export_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    test_id: UUID,
) -> ExportTestApiResponse:
    """Test export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_tests → test metadata for given test_id
      3. search_test_invocation_entries_internal → invocations for this test
      4. search_test_invocation_runs → runs for these invocations
      5. Parallel resource hydration → human-readable values
      6. Generate ZIP (tests.csv + invocations.csv + runs.csv) + create upload entry
    """

    # -- Step 1: Profile context --
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search test metadata --
    async with pool.acquire() as conn:
        tests, _total = await search_tests(conn, test_ids=[test_id], limit=1)

    # -- Step 3: Search invocations for this test --
    async with pool.acquire() as conn:
        invocations, _total_count = await search_test_invocation_entries_internal(
            conn, test_ids=[test_id], limit=100000, offset=0
        )

    # -- Step 4: Search runs for these invocations --
    invocation_ids = [inv.invocation_id for inv in invocations]
    if invocation_ids:
        async with pool.acquire() as conn:
            runs = (
                await search_test_invocation_runs(
                    conn, test_invocation_ids=invocation_ids, limit=100000, offset=0
                )
            )[0]
    else:
        runs = []

    if not tests and not invocations and not runs:
        return ExportTestApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 5: Parallel resource hydration --
    all_name_ids: set[UUID] = set()
    all_department_ids: set[UUID] = set()
    all_voice_ids: set[UUID] = set()

    for t in tests:
        all_department_ids.update(t.department_ids or [])
        if t.eval_id:
            all_name_ids.add(t.eval_id)

    for inv in invocations:
        all_name_ids.update(inv.agent_ids or [])
        all_department_ids.update(inv.department_ids or [])
        if inv.voice_id:
            all_voice_ids.add(inv.voice_id)

    for r in runs:
        all_name_ids.update(r.agent_ids or [])
        all_name_ids.update(r.prompt_ids or [])
        all_name_ids.update(r.instruction_ids or [])
        all_name_ids.update(r.tool_ids or [])
        all_voice_ids.update(r.voice_ids or [])

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as c:
            return await get_names(c, list(all_name_ids), redis)

    async def _fetch_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as c:
            return await get_departments(c, list(all_department_ids), redis)

    async def _fetch_voices() -> list:
        if not all_voice_ids:
            return []
        async with pool.acquire() as c:
            return await get_voices(c, list(all_voice_ids), redis)

    names_data, departments_data, voices_data = await asyncio.gather(
        _fetch_names(),
        _fetch_departments(),
        _fetch_voices(),
    )

    name_map: dict[UUID, str] = {n.id: n.name for n in names_data}
    department_map: dict[UUID, str] = {d.id: d.name or "" for d in departments_data}
    voice_map: dict[UUID, str] = {v.id: v.voice for v in voices_data}

    # -- Step 6: Generate CSVs --

    # tests.csv
    test_output = io.StringIO()
    test_writer = csv.writer(test_output)
    test_writer.writerow(TEST_CSV_COLUMNS)

    for t in tests:
        departments_str = PIPE.join(
            department_map.get(did, str(did)) for did in (t.department_ids or [])
        )

        test_writer.writerow(
            [
                str(t.test_id),
                name_map.get(t.eval_id, str(t.eval_id)) if t.eval_id else "",
                str(t.profile_id) if t.profile_id else "",
                departments_str,
                t.test_name,
                t.test_description,
                str(t.num_invocations),
                "Yes" if t.infinite_mode else "No",
                "Yes" if t.is_dynamic else "No",
                "Yes" if t.archived else "No",
                str(t.test_created_at),
            ]
        )

    # invocations.csv
    inv_output = io.StringIO()
    inv_writer = csv.writer(inv_output)
    inv_writer.writerow(INVOCATION_CSV_COLUMNS)

    for inv in invocations:
        agents_str = PIPE.join(
            name_map.get(aid, str(aid)) for aid in (inv.agent_ids or [])
        )
        departments_str = PIPE.join(
            department_map.get(did, str(did)) for did in (inv.department_ids or [])
        )
        modality_ids_str = PIPE.join(str(mid) for mid in (inv.modality_ids or []))

        inv_writer.writerow(
            [
                str(inv.invocation_id),
                str(inv.test_id) if inv.test_id else "",
                str(inv.group_id) if inv.group_id else "",
                str(inv.invocation_created_at),
                inv.invocation_title,
                "Yes" if inv.use_custom else "No",
                str(inv.position),
                "Yes" if inv.invocation_completed else "No",
                str(inv.grade_id) if inv.grade_id else "",
                str(inv.grade_score) if inv.grade_score is not None else "",
                "Yes" if inv.grade_passed else "No",
                str(inv.grade_time_taken) if inv.grade_time_taken is not None else "",
                str(inv.rubric_id) if inv.rubric_id else "",
                agents_str,
                str(inv.quality_id) if inv.quality_id else "",
                departments_str,
                voice_map.get(inv.voice_id, str(inv.voice_id)) if inv.voice_id else "",
                str(inv.temperature_level_id) if inv.temperature_level_id else "",
                str(inv.reasoning_level_id) if inv.reasoning_level_id else "",
                modality_ids_str,
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
                PIPE.join(name_map.get(aid, str(aid)) for aid in (r.agent_ids or [])),
                PIPE.join(voice_map.get(vid, str(vid)) for vid in (r.voice_ids or [])),
                PIPE.join(name_map.get(pid, str(pid)) for pid in (r.prompt_ids or [])),
                PIPE.join(
                    name_map.get(iid, str(iid)) for iid in (r.instruction_ids or [])
                ),
                PIPE.join(name_map.get(tid, str(tid)) for tid in (r.tool_ids or [])),
                str(r.created_at),
                "Yes" if r.active else "No",
            ]
        )

    # -- Step 7: Generate ZIP --
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tests.csv", test_output.getvalue())
        zf.writestr("invocations.csv", inv_output.getvalue())
        zf.writestr("runs.csv", run_output.getvalue())

    zip_content = zip_buffer.getvalue()
    row_count = len(tests) + len(invocations) + len(runs)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"test_export_{timestamp}.zip"

    return ExportTestApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
