"""Reports export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_test_invocation_entries_internal — full dump
  3. search_test_invocation_traces — full dump
  4. search_test_invocation_runs — full dump
  5. Resource get tools — parallel hydration (names, departments, voices)
  6. ZIP generation (invocations.csv + groups.csv + runs.csv + brightspace.csv) + upload entry
"""

from __future__ import annotations

import asyncio
import base64
import io
import zipfile
from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.entries.test_invocation.types import GetTestInvocationResponse
from app.tools.entries.test_invocation_runs.search import (
    search_test_invocation_runs,
)
from app.tools.entries.test_invocation_runs.types import (
    GetTestInvocationRunsResponse,
)
from app.tools.entries.test_invocation_traces.search import (
    search_test_invocation_traces,
)
from app.tools.entries.test_invocation_traces.types import (
    GetTestInvocationTracesResponse,
)
from app.tools.resources.departments.get import get_departments
from app.tools.resources.names.get import get_names
from app.tools.resources.voices.get import get_voices
from app.utils.csv.formula_safe import FormulaSafeWriter

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


from app.infra.reports.types import ExportReportsApiResponse


async def _empty_list() -> list:  # type: ignore[type-arg]
    return []


def _build_invocations_csv(
    invocations: list,
    name_map: dict[UUID, str],
    department_map: dict[UUID, str],
    voice_map: dict[UUID, str],
) -> str:
    inv_output = io.StringIO()
    inv_writer = FormulaSafeWriter(inv_output)
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
    return inv_output.getvalue()


def _build_groups_csv(
    groups: list[GetTestInvocationTracesResponse],
    invocation_by_id: dict[UUID, GetTestInvocationResponse],
    name_map: dict[UUID, str],
    voice_map: dict[UUID, str],
) -> str:
    grp_output = io.StringIO()
    grp_writer = FormulaSafeWriter(grp_output)
    grp_writer.writerow(GROUP_CSV_COLUMNS)

    for g in groups:
        # Traces (groups) carry the config bundle (voices/prompts/instructions/
        # tools); agents live on the parent invocation, not the trace (#102).
        parent_inv = invocation_by_id.get(g.test_invocation_id)
        agent_ids = parent_inv.agent_ids if parent_inv else []
        grp_writer.writerow(
            [
                str(g.id),
                str(g.test_invocation_id),
                PIPE.join(name_map.get(aid, "") for aid in (agent_ids or [])),
                PIPE.join(voice_map.get(vid, "") for vid in (g.voice_ids or [])),
                PIPE.join(name_map.get(pid, "") for pid in (g.prompt_ids or [])),
                PIPE.join(name_map.get(iid, "") for iid in (g.instruction_ids or [])),
                PIPE.join(name_map.get(tid, "") for tid in (g.tool_ids or [])),
                str(g.created_at),
                "Yes" if g.active else "No",
            ]
        )
    return grp_output.getvalue()


def _build_runs_csv(
    runs: list[GetTestInvocationRunsResponse],
    invocation_by_id: dict[UUID, GetTestInvocationResponse],
    trace_by_id: dict[UUID, GetTestInvocationTracesResponse],
    name_map: dict[UUID, str],
    voice_map: dict[UUID, str],
) -> str:
    run_output = io.StringIO()
    run_writer = FormulaSafeWriter(run_output)
    run_writer.writerow(RUN_CSV_COLUMNS)

    for r in runs:
        # Runs are pure binding rows after #102: agents come from the parent
        # invocation (via test_invocation_id); the config bundle (voices/
        # prompts/instructions/tools) comes from the linked trace (via
        # test_invocation_traces_id). Runs carry none of these fields.
        parent_inv = invocation_by_id.get(r.test_invocation_id)
        run_trace = (
            trace_by_id.get(r.test_invocation_traces_id)
            if r.test_invocation_traces_id is not None
            else None
        )
        agent_ids = parent_inv.agent_ids if parent_inv else []
        voice_ids = run_trace.voice_ids if run_trace else []
        prompt_ids = run_trace.prompt_ids if run_trace else []
        instruction_ids = run_trace.instruction_ids if run_trace else []
        tool_ids = run_trace.tool_ids if run_trace else []
        run_writer.writerow(
            [
                str(r.id),
                str(r.test_invocation_id),
                PIPE.join(name_map.get(aid, "") for aid in (agent_ids or [])),
                PIPE.join(voice_map.get(vid, "") for vid in (voice_ids or [])),
                PIPE.join(name_map.get(pid, "") for pid in (prompt_ids or [])),
                PIPE.join(name_map.get(iid, "") for iid in (instruction_ids or [])),
                PIPE.join(name_map.get(tid, "") for tid in (tool_ids or [])),
                str(r.created_at),
                "Yes" if r.active else "No",
            ]
        )
    return run_output.getvalue()


def _build_brightspace_csv(
    invocations: list,
    name_map: dict[UUID, str],
) -> str:
    """Build the Brightspace gradebook CSV — one row per graded invocation."""
    bs_output = io.StringIO()
    bs_writer = FormulaSafeWriter(bs_output)
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
    return bs_output.getvalue()


async def export_reports_impl(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    mode: str | None = None,
) -> ExportReportsApiResponse:
    """Reports export — view-aware sub-modes via ``mode``.

    Modes:
      - ``None`` / ``"full"`` → ZIP with invocations/groups/runs/brightspace CSVs
      - ``"brightspace"`` → brightspace.csv only (no ZIP)
    """

    # -- Step 1: Profile context --
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Authorization (was the missed sibling of #404) --
    #
    # The #404 systemic export gate only requires the bare ``attempt:export``
    # capability (which GTA/UTA/Guest hold via _READ_OPS). But the reports view
    # exports test-invocation + Brightspace-grade data that the on-screen read
    # (resolve_reports_context) gates behind the stronger ``attempt:report``
    # (an _ATTEMPT_VIEW_OP held only by top tiers) AND scopes to
    # ``resolve_visible_profile_ids``. Without both, a low-tier user blocked
    # from /attempt/report on-screen could export every department's reports.
    #   (1) require the same ``attempt:report`` capability as the read;
    #   (2) clamp the dump to the actor's departments (superadmin/role_level 0
    #       unconstrained) — the invocation search drives the groups/runs/
    #       brightspace CSVs (fetched by its invocation_ids), so clamping it
    #       clamps the whole export, mirroring the read's visible scope.
    from app.infra.permissions_helpers import has_permission

    if not has_permission(profile.role_permissions, "attempt", "report"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to export reports.",
        )

    dept_clamp = None if profile.role_level == 0 else (profile.department_ids or [])

    # -- Step 2: Search test invocations (scoped to the actor's departments) --
    async with pool.acquire() as conn:
        invocations, _total_count = await search_test_invocation_entries_internal(
            conn, redis, suite_department_ids=dept_clamp, limit=100000, offset=0
        )

    if not invocations:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        if mode == "brightspace":
            return ExportReportsApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )
        return ExportReportsApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    # ── Mode: brightspace (CSV only) ─────────────────────────────────────────
    if mode == "brightspace":
        # Only need names for agent labels.
        all_name_ids: set[UUID] = set()
        for inv in invocations:
            all_name_ids.update(inv.agent_ids or [])

        names_data = (
            await get_names(pool, list(all_name_ids), redis) if all_name_ids else []
        )
        name_map: dict[UUID, str] = {n.id: n.name for n in names_data}

        bs_content_str = _build_brightspace_csv(invocations, name_map)
        bs_bytes = bs_content_str.encode("utf-8")
        content = base64.b64encode(bs_bytes).decode("ascii")
        graded_rows = sum(1 for inv in invocations if inv.grade_score is not None)
        return ExportReportsApiResponse(
            content=content,
            file_name=f"brightspace_{timestamp}.csv",
            mime_type="text/csv",
            row_count=graded_rows,
        )

    # ── Mode: full / default (ZIP with all 4 CSVs) ───────────────────────────

    # -- Step 3: Search groups and runs --
    invocation_ids = [inv.invocation_id for inv in invocations]

    async def _fetch_groups() -> tuple[list, int]:
        async with pool.acquire() as conn:
            return await search_test_invocation_traces(
                conn, redis, test_invocation_ids=invocation_ids, limit=100000, offset=0
            )

    async def _fetch_runs() -> tuple[list, int]:
        async with pool.acquire() as conn:
            return await search_test_invocation_runs(
                conn, redis, test_invocation_ids=invocation_ids, limit=100000, offset=0
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

    # Agent ids live on the parent invocation; voice (single) also on invocation.
    for inv in invocations:
        all_name_ids.update(inv.agent_ids or [])
        all_department_ids.update(inv.department_ids or [])
        if inv.voice_id:
            all_voice_ids.add(inv.voice_id)

    # The config bundle (voices/prompts/instructions/tools) lives on traces
    # (groups); traces carry no agent_ids (those came from invocations above).
    for g in groups:
        all_name_ids.update(g.prompt_ids or [])
        all_name_ids.update(g.instruction_ids or [])
        all_name_ids.update(g.tool_ids or [])
        all_voice_ids.update(g.voice_ids or [])

    # Runs are pure binding rows after #102 — they carry no name/voice ids of
    # their own. Their displayed ids are sourced from the parent invocation
    # (agents) and linked trace (bundle), both already collected above.

    async def _get_names() -> list:
        if not all_name_ids:
            return []
        return await get_names(pool, list(all_name_ids), redis)

    async def _get_departments() -> list:
        if not all_department_ids:
            return []
        return await get_departments(pool, list(all_department_ids), redis)

    async def _get_voices() -> list:
        if not all_voice_ids:
            return []
        return await get_voices(pool, list(all_voice_ids), redis)

    names_data, departments_data, voices_data = await asyncio.gather(
        _get_names(),
        _get_departments(),
        _get_voices(),
    )

    name_map = {n.id: n.name for n in names_data}
    department_map: dict[UUID, str] = {d.id: d.name or "" for d in departments_data}
    voice_map: dict[UUID, str] = {v.id: v.voice for v in voices_data}

    # Lookups so trace/run rows can source ids from the model that owns them:
    # agents from the parent invocation, the config bundle from the linked trace.
    invocation_by_id: dict[UUID, GetTestInvocationResponse] = {
        inv.invocation_id: inv for inv in invocations
    }
    trace_by_id: dict[UUID, GetTestInvocationTracesResponse] = {
        g.id: g for g in groups
    }

    # -- Step 5: Generate CSVs via helpers --
    inv_csv = _build_invocations_csv(invocations, name_map, department_map, voice_map)
    grp_csv = _build_groups_csv(groups, invocation_by_id, name_map, voice_map)
    run_csv = _build_runs_csv(
        runs, invocation_by_id, trace_by_id, name_map, voice_map
    )
    bs_csv = _build_brightspace_csv(invocations, name_map)

    # -- Step 6: Generate ZIP --
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("invocations.csv", inv_csv)
        zf.writestr("groups.csv", grp_csv)
        zf.writestr("runs.csv", run_csv)
        zf.writestr("brightspace.csv", bs_csv)

    zip_content = zip_buffer.getvalue()
    row_count = len(invocations) + len(groups) + len(runs)

    content = base64.b64encode(zip_content).decode("ascii")
    file_name = f"reports_export_{timestamp}.zip"

    return ExportReportsApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
