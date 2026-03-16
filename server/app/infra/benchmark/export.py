"""Benchmark export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_benchmarks — full dump (all entries)
  3. search_test_invocation_entries_internal — full dump of test invocations
  4. Resource get tools — parallel hydration (departments, profiles)
  5. ZIP generation (benchmarks.csv + test_invocations.csv) + upload entry creation
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
from app.tools.entries.benchmark.search import search_benchmarks
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.resources.departments.get import get_departments
from app.tools.resources.profiles.get import get_profiles

PIPE = "|"

BENCHMARK_CSV_COLUMNS = [
    "benchmark_id",
    "eval_ids",
    "profile_ids",
    "department_ids",
    "created_at",
    "updated_at",
    "active",
    "use_groups",
    "dynamic",
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
    "run_agent_ids",
    "group_agent_ids",
    "voice_id",
    "temperature_level_id",
    "reasoning_level_id",
    "modality_ids",
]


class ExportBenchmarkApiResponse(BaseModel):
    """Response model for benchmark export."""

    content: str
    file_name: str
    mime_type: str
    row_count: int


async def _empty_list() -> list:  # type: ignore[type-arg]
    return []


async def export_benchmark_impl(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
) -> ExportBenchmarkApiResponse:
    """Benchmark full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_benchmarks → all entries (full dump)
      3. search_test_invocation_entries_internal → all test invocations
      4. Parallel resource hydration → human-readable values
      5. Generate ZIP (benchmarks.csv + test_invocations.csv) and return base64-encoded content
    """

    # -- Step 1: Profile context --
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search all benchmarks (full dump) --
    async with pool.acquire() as conn:
        benchmarks = await search_benchmarks(conn, limit=100000)

    # -- Step 3: Search all test invocations (full dump) --
    async with pool.acquire() as conn:
        invocations, _total_count = await search_test_invocation_entries_internal(
            conn, limit=100000, offset=0
        )

    if not benchmarks and not invocations:
        return ExportBenchmarkApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 4: Parallel resource hydration --
    all_department_ids: set[UUID] = set()
    all_profile_ids: set[UUID] = set()

    for b in benchmarks:
        all_department_ids.update(b.department_ids or [])
        all_profile_ids.update(b.profile_ids or [])

    for inv in invocations:
        all_department_ids.update(inv.department_ids or [])

    async def _get_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as conn:
            return await get_departments(conn, list(all_department_ids), redis)

    async def _get_profiles() -> list:
        if not all_profile_ids:
            return []
        async with pool.acquire() as conn:
            return await get_profiles(conn, list(all_profile_ids), redis)

    departments_data, profiles_data = await asyncio.gather(
        _get_departments(),
        _get_profiles(),
    )

    department_map: dict[UUID, str] = {d.id: d.name or "" for d in departments_data}
    profile_map: dict[UUID, str] = {p.id: p.name or "" for p in profiles_data}

    # -- Step 5: Generate CSVs --

    # benchmarks.csv
    bench_output = io.StringIO()
    bench_writer = csv.writer(bench_output)
    bench_writer.writerow(BENCHMARK_CSV_COLUMNS)

    for b in benchmarks:
        eval_ids_str = PIPE.join(str(eid) for eid in (b.eval_ids or []))
        profile_ids_str = PIPE.join(
            profile_map.get(pid, str(pid)) for pid in (b.profile_ids or [])
        )
        department_ids_str = PIPE.join(
            department_map.get(did, str(did)) for did in (b.department_ids or [])
        )

        bench_writer.writerow(
            [
                str(b.benchmark_id),
                eval_ids_str,
                profile_ids_str,
                department_ids_str,
                str(b.created_at),
                str(b.updated_at),
                "Yes" if b.active else "No",
                "Yes" if b.use_groups else "No",
                "Yes" if b.dynamic else "No",
            ]
        )

    # test_invocations.csv
    inv_output = io.StringIO()
    inv_writer = csv.writer(inv_output)
    inv_writer.writerow(INVOCATION_CSV_COLUMNS)

    for inv in invocations:
        agents_str = PIPE.join(str(aid) for aid in (inv.agent_ids or []))
        departments_str = PIPE.join(
            department_map.get(did, str(did)) for did in (inv.department_ids or [])
        )
        run_agent_ids_str = PIPE.join(str(aid) for aid in (inv.run_agent_ids or []))
        group_agent_ids_str = PIPE.join(str(aid) for aid in (inv.group_agent_ids or []))
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
                run_agent_ids_str,
                group_agent_ids_str,
                str(inv.voice_id) if inv.voice_id else "",
                str(inv.temperature_level_id) if inv.temperature_level_id else "",
                str(inv.reasoning_level_id) if inv.reasoning_level_id else "",
                modality_ids_str,
            ]
        )

    # -- Step 6: Generate ZIP + upload --
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("benchmarks.csv", bench_output.getvalue())
        zf.writestr("test_invocations.csv", inv_output.getvalue())

    zip_content = zip_buffer.getvalue()
    row_count = len(benchmarks) + len(invocations)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"benchmark_export_{timestamp}.zip"

    return ExportBenchmarkApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
