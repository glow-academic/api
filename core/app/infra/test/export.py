"""Test export logic — view-aware, canonical file-modality output.

A single artifact-level endpoint dispatches to per-view exports by ``view``.
Views: ``single`` (one test), ``benchmark`` (analytics), ``invocation``.
Every view returns the canonical ``{file_id, file_name, row_count}`` shape;
:func:`app.infra.exports.file_modality.wrap_bytes_as_file` runs the 4-step
file-modality chain. Client downloads via ``/api/test/download/{file_id}``.

Per-view byte extraction: ``benchmark`` and ``invocation`` impls return a
Pydantic envelope with base64-encoded ``content``. We call them directly
(skipping the per-view route layer to avoid double auth/audit) and decode
the base64 here. The ``single`` view keeps its existing tests/invocations/runs
ZIP logic but now wraps the raw bytes through the canonical helper.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import zipfile
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.exports.file_modality import (
    accept_staged_export,
    extension_from_mime,
    stage_export_soft_call,
    wrap_bytes_as_file,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
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


# =============================================================================
# View dispatcher
# =============================================================================


async def export_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    view: str = "single",
    test_id: UUID | None = None,
    invocation_id: UUID | None = None,
    draft_id: UUID | None = None,
    mode: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
    **_kwargs,
):
    """Dispatch on ``view`` and return canonical ``ExportTestApiResponse``."""
    from app.infra.test.types import ExportTestApiResponse

    # ── Short-circuit: ack — activate/reject a staged export ─────────────
    if accept is not None and idempotency_key is not None:
        file_id, file_name, row_count = await accept_staged_export(
            pool, redis, artifact="test",
            idempotency_key=idempotency_key, accept=accept,
        )
        return ExportTestApiResponse(
            file_id=file_id, file_name=file_name, row_count=row_count,
            idempotency_key=idempotency_key,
        )

    if view == "single":
        if test_id is None:
            raise HTTPException(
                status_code=400,
                detail="test_id is required for view='single'.",
            )
        bytes_, row_count = await _export_single_test_bytes(
            pool, redis, profile_id=profile_id, test_id=test_id,
        )
        wrapped = await wrap_bytes_as_file(
            pool,
            redis,
            content=bytes_,
            file_name_prefix="test_export",
            mime_type="application/zip",
            extension="zip",
            session_id=session_id,
            soft=soft,
        )
        if soft and call_id is not None:
            await stage_export_soft_call(
                pool, redis, artifact="test", call_id=call_id,
                wrapped=wrapped, row_count=row_count,
            )
        return ExportTestApiResponse(
            file_id=wrapped.file_id, file_name=wrapped.file_name,
            row_count=row_count, idempotency_key=call_id,
        )

    if view == "benchmark":
        from app.infra.benchmark.export import export_benchmark_impl
        envelope = await export_benchmark_impl(pool, redis, profile_id=profile_id)
    elif view == "invocation":
        if test_id is None:
            raise HTTPException(
                status_code=400,
                detail="test_id is required for view='invocation'.",
            )
        # The per-view impl needs a group_id, like the per-view route.
        from app.infra.invocation.export import export_invocation_impl
        from app.infra.test.group import group_test_impl
        group_result = await group_test_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        envelope = await export_invocation_impl(
            pool,
            redis,
            profile_id=profile_id,
            test_id=test_id,
            group_id=group_result.group_id,
            invocation_entry_id=invocation_id,
            draft_id=draft_id,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown test export view: {view!r}")

    return await _wrap_envelope(
        pool, redis, envelope, view_prefix=f"test_{view}_export", session_id=session_id,
        soft=soft, call_id=call_id,
    )


# =============================================================================
# Helpers
# =============================================================================


async def _wrap_envelope(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    envelope,
    *,
    view_prefix: str,
    session_id: UUID | None,
    soft: bool = False,
    call_id: UUID | None = None,
):
    """Decode per-view base64 envelope + run canonical file-modality chain."""
    from app.infra.test.types import ExportTestApiResponse

    raw_b64 = getattr(envelope, "content", "") or ""
    bytes_ = base64.b64decode(raw_b64) if raw_b64 else b""
    mime_type = getattr(envelope, "mime_type", "application/zip") or "application/zip"
    row_count = int(getattr(envelope, "row_count", 0) or 0)

    wrapped = await wrap_bytes_as_file(
        pool,
        redis,
        content=bytes_,
        file_name_prefix=view_prefix,
        mime_type=mime_type,
        extension=extension_from_mime(mime_type),
        session_id=session_id,
        soft=soft,
    )
    if soft and call_id is not None:
        await stage_export_soft_call(
            pool, redis, artifact="test", call_id=call_id,
            wrapped=wrapped, row_count=row_count,
        )
    return ExportTestApiResponse(
        file_id=wrapped.file_id, file_name=wrapped.file_name,
        row_count=row_count, idempotency_key=call_id,
    )


async def _export_single_test_bytes(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    test_id: UUID,
) -> tuple[bytes, int]:
    """Build the single-test ZIP (tests.csv + invocations.csv + runs.csv); return (bytes, row_count)."""

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    with timed("resolve_test"):
      async with pool.acquire() as conn:
        tests, _total = await search_tests(conn, redis, test_ids=[test_id], limit=1)

    async with pool.acquire() as conn:
        invocations, _total_count = await search_test_invocation_entries_internal(
            conn, redis, test_ids=[test_id], limit=100000, offset=0
        )

    invocation_ids = [inv.invocation_id for inv in invocations]
    if invocation_ids:
        async with pool.acquire() as conn:
            runs = (
                await search_test_invocation_runs(
                    conn, redis, test_invocation_ids=invocation_ids, limit=100000, offset=0
                )
            )[0]
    else:
        runs = []

    if not tests and not invocations and not runs:
        empty = io.BytesIO()
        with zipfile.ZipFile(empty, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("tests.csv", "")
        return empty.getvalue(), 0

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
        return await get_names(pool, list(all_name_ids), redis)

    async def _fetch_departments() -> list:
        if not all_department_ids:
            return []
        return await get_departments(pool, list(all_department_ids), redis)

    async def _fetch_voices() -> list:
        if not all_voice_ids:
            return []
        async with pool.acquire() as c:
            return await get_voices(c, list(all_voice_ids), redis)

    with timed("hydrate"):
      names_data, departments_data, voices_data = await asyncio.gather(
        _fetch_names(),
        _fetch_departments(),
        _fetch_voices(),
    )

    name_map: dict[UUID, str] = {n.id: n.name for n in names_data}
    department_map: dict[UUID, str] = {d.id: d.name or "" for d in departments_data}
    voice_map: dict[UUID, str] = {v.id: v.voice for v in voices_data}

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

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tests.csv", test_output.getvalue())
        zf.writestr("invocations.csv", inv_output.getvalue())
        zf.writestr("runs.csv", run_output.getvalue())

    return zip_buffer.getvalue(), len(tests) + len(invocations) + len(runs)
