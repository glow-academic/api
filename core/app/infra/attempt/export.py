"""Attempt export logic — view-aware, canonical file-modality output.

A single artifact-level endpoint dispatches to per-view exports by ``view``.
Every view returns the canonical ``{file_id, file_name, row_count}`` shape;
the helper :func:`app.infra.exports.file_modality.wrap_bytes_as_file` runs the
4-step file-modality chain (uploads_entry + files_resource + files_entry +
file_uploads junction + refresh) and returns the ``file_id`` for download via
``/attempt/file/download`` (BFF: ``/api/attempt/download/{file_id}``).

Per-view CSV/ZIP byte extraction strategy: every per-view impl returns a
Pydantic envelope with base64-encoded ``content`` (see e.g.
``ExportDashboardApiResponse``). We call those impls directly (no per-view
route layer — avoid double auth/audit) and decode the base64 here. The
single-view path keeps its existing attempts/chats/messages ZIP logic but
now wraps the bytes through the file-modality helper.
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
from app.infra.attempt.permissions import check_attempt_access
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
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


# =============================================================================
# View dispatcher
# =============================================================================


async def export_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    view: str = "single",
    attempt_id: UUID | None = None,
    record_id: UUID | None = None,
    mode: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
    **_kwargs,
):
    """Dispatch on ``view`` and return canonical ``ExportAttemptApiResponse``.

    ``view``:
      - ``single``    → one attempt's ZIP (legacy single-attempt export)
      - ``dashboard`` → analytics dashboard export
      - ``reports``   → analytics reports export
      - ``leaderboard`` → leaderboard export
      - ``home``      → home page certificate export
      - ``practice``  → practice page export
      - ``record``    → analytics record export (one target profile)
      - ``report``    → analytics single-report export (alias for reports)
    """
    from app.infra.attempt.types import ExportAttemptApiResponse

    # ── Short-circuit: ack — activate/reject a staged export ─────────────
    if accept is not None and idempotency_key is not None:
        file_id, file_name, row_count = await accept_staged_export(
            pool, redis, artifact="attempt",
            idempotency_key=idempotency_key, accept=accept,
        )
        return ExportAttemptApiResponse(
            file_id=file_id, file_name=file_name, row_count=row_count,
            idempotency_key=idempotency_key,
        )

    # ── Single-attempt view ──────────────────────────────────────────────
    if view == "single":
        if attempt_id is None:
            raise HTTPException(
                status_code=400,
                detail="attempt_id is required for view='single'.",
            )
        with timed("single_attempt_build"):
            bytes_, row_count = await _export_single_attempt_bytes(
                pool, redis, profile_id=profile_id, attempt_id=attempt_id,
            )
        with timed("wrap_as_file"):
         wrapped = await wrap_bytes_as_file(
            pool,
            redis,
            content=bytes_,
            file_name_prefix="attempt_export",
            mime_type="application/zip",
            extension="zip",
            session_id=session_id,
            soft=soft,
        )
        if soft and call_id is not None:
            await stage_export_soft_call(
                pool, redis, artifact="attempt", call_id=call_id,
                wrapped=wrapped, row_count=row_count,
            )
        return ExportAttemptApiResponse(
            file_id=wrapped.file_id, file_name=wrapped.file_name,
            row_count=row_count, idempotency_key=call_id,
        )

    # ── Analytics views (delegate to per-view impl, decode base64) ────────
    if view == "dashboard":
        from app.infra.dashboard.export import export_dashboard_impl
        envelope = await export_dashboard_impl(pool, redis, profile_id=profile_id)
    elif view == "reports" or view == "report":
        from app.infra.reports.export import export_reports_impl
        envelope = await export_reports_impl(pool, redis, profile_id=profile_id, mode=mode)
    elif view == "leaderboard":
        from app.infra.leaderboard.export import export_leaderboard_impl
        envelope = await export_leaderboard_impl(pool, redis, profile_id=profile_id)
    elif view == "home":
        from app.infra.home_export import export_home_client
        envelope = await export_home_client(pool, redis, profile_id=profile_id, mode=mode)
    elif view == "practice":
        from app.infra.practice_export import export_practice_client
        envelope = await export_practice_client(pool, redis, profile_id=profile_id)
    elif view == "record":
        if record_id is None:
            raise HTTPException(
                status_code=400,
                detail="record_id is required for view='record'.",
            )
        from app.infra.record_export import export_record_client
        envelope = await export_record_client(
            pool, redis, profile_id=profile_id, target_profile_id=record_id,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown attempt export view: {view!r}")

    return await _wrap_envelope(
        pool, redis, envelope, view_prefix=f"attempt_{view}_export", session_id=session_id,
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
    from app.infra.attempt.types import ExportAttemptApiResponse

    raw_b64 = getattr(envelope, "content", "") or ""
    if not raw_b64:
        # Empty per-view result — still produce a valid (empty) file so the
        # client download flow stays uniform.
        bytes_ = b""
    else:
        bytes_ = base64.b64decode(raw_b64)

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
            pool, redis, artifact="attempt", call_id=call_id,
            wrapped=wrapped, row_count=row_count,
        )
    return ExportAttemptApiResponse(
        file_id=wrapped.file_id, file_name=wrapped.file_name,
        row_count=row_count, idempotency_key=call_id,
    )


async def _export_single_attempt_bytes(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    attempt_id: UUID,
) -> tuple[bytes, int]:
    """Build the single-attempt ZIP (attempts.csv + chats.csv + messages.csv) and return (bytes, row_count)."""

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    async def _fetch_attempts() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_attempts(
                c, redis, attempt_ids=[attempt_id], limit=1
            )
            return items

    async def _fetch_chats() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_attempt_chats(
                c, redis, attempt_ids=[attempt_id], limit=100000
            )
            return items

    async def _fetch_messages() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_attempt_messages(
                c, redis, attempt_ids=[attempt_id], limit=100000
            )
            return items

    with timed("fetch_gather"):
        attempts, chats, messages = await asyncio.gather(
            _fetch_attempts(),
            _fetch_chats(),
            _fetch_messages(),
        )

    if not attempts:
        # Empty ZIP, zero rows — still passes through the file-modality chain.
        empty = io.BytesIO()
        with zipfile.ZipFile(empty, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("attempts.csv", "")
        return empty.getvalue(), 0

    # Authorization: gate the target attempt the same way the on-screen sibling
    # ``get_attempt_internal`` does (``app/infra/attempt/get.py``). Access is
    # own-attempt OR strictly-higher role (guests/members see only their own;
    # superadmin sees all). Without this, any holder of ``attempt:export`` could
    # export any student's attempt/grade/PII by ``attempt_id`` (IDOR, #150).
    # ``attempt_role`` is None because role was dropped from profiles_resource
    # (mirrors get.py — owner role is no longer available on the attempt MV).
    if not check_attempt_access(
        attempts[0].profile_id,
        profile.profiles_id,
        request_role=profile.role,
        attempt_role=None,
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to export this attempt.",
        )

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
        return await get_profiles(pool, list(all_profile_ids), redis)

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

    profile_map = {p.id: p.name or "" for p in profiles_data}
    simulation_map = {s.id: s.name or "" for s in simulations_data}
    scenario_map = {s.id: s.name or "" for s in scenarios_data}
    persona_map = {p.id: p.name or "" for p in personas_data}

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
                "",
                "",
                "Yes" if a.practice else "No",
                "Yes" if a.infinite_mode else "No",
                str(a.num_chats),
                "Yes" if a.is_archived else "No",
            ]
        )

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

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("attempts.csv", attempts_output.getvalue())
        zf.writestr("chats.csv", chats_output.getvalue())
        zf.writestr("messages.csv", messages_output.getvalue())

    return zip_buffer.getvalue(), len(attempts) + len(chats) + len(messages)
