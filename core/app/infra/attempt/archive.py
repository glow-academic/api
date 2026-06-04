"""Bulk archive/unarchive attempts.

Resolves attempt ids (either explicit list or filter-based search),
writes one archive entry per attempt, and returns the affected
``profile_ids`` so the caller can invalidate the right caches.

Soft/accept (stage-inactive, bulk): ``soft=True`` creates all archive rows
dormant (``active=False``) + a pending ``soft_calls_entry`` whose ``patch`` holds
the list of archive ids; the ack ({idempotency_key, accept}) activates them all
(``activate_rows`` with the list) or rejects. Lets a benchmark scenario stage a
bulk archive and commit it on accept. ``soft=False`` archives immediately.

Routes/attempt/archive.py is a thin HTTP adapter over ``archive_attempt_impl``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.attempt.group import group_attempt_impl
from app.infra.attempt.permissions import check_attempt_access
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_archive.create import create_attempt_archive
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call

ARTIFACT = "attempt"
OPERATION = "archive"


class ArchiveAttemptsRequest(BaseModel):
    archived: bool = Field(..., description="Whether to archive (true) or unarchive (false)")
    attempt_ids: list[UUID] | None = Field(default_factory=list, description="Specific attempt UUIDs to archive")  # type: ignore[arg-type]
    start_date: str | None = Field(None, description="Start date for filter-based archive")
    end_date: str | None = Field(None, description="End date for filter-based archive")
    cohort_ids: list[UUID] | None = Field(default_factory=list, description="Cohort UUIDs to filter by")  # type: ignore[arg-type]
    department_ids: list[UUID] | None = Field(default_factory=list, description="Department UUIDs to filter by")  # type: ignore[arg-type]
    simulation_ids: list[UUID] | None = Field(default_factory=list, description="Simulation UUIDs to filter by")  # type: ignore[arg-type]
    scenario_ids: list[UUID] | None = Field(default_factory=list, description="Scenario UUIDs to filter by")  # type: ignore[arg-type]
    profile_ids_filter: list[UUID] | None = Field(default_factory=list, description="Profile UUIDs to filter by")  # type: ignore[arg-type]
    infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior call; on the ack, the server-minted soft key to activate/reject a staged archive")
    soft: bool = Field(False, description="Stage the archive dormant (active=False); accept activates the whole set")
    accept: bool | None = Field(None, description="Ack: True activates the staged archive, False rejects. Only meaningful with idempotency_key")


class ArchiveAttemptsResponse(BaseModel):
    updated_count: int = Field(0, description="Number of attempts updated")
    profile_ids_to_invalidate: list[str] | None = Field(None, description="Profile IDs whose caches need invalidation")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key (audit call_id). On a soft propose, echo this back with accept to activate/reject the staged archive.")


class MissingFilterError(ValueError):
    """Raised when neither attempt_ids nor a date range is provided."""


async def archive_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: ArchiveAttemptsRequest,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> ArchiveAttemptsResponse:
    """Bulk archive or unarchive attempts (simulation or benchmark), with soft/accept."""
    # ── Short-circuit: ack — activate / reject the staged archive set ──
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(status_code=404, detail="No pending archive for this call.")
        ids = entry.patch or {}
        archive_ids = [UUID(x) for x in ids.get("archive_ids", [])]
        if accept and archive_ids:
            async with pool.acquire() as conn:
                await activate_rows(conn, table="attempt_archive_entry", ids=archive_ids)
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                operation=OPERATION, artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        return ArchiveAttemptsResponse(
            updated_count=int(ids.get("updated_count", 0)),
            profile_ids_to_invalidate=list(ids.get("profile_ids", [])),
            idempotency_key=idempotency_key,
        )

    has_attempt_ids = bool(request.attempt_ids and len(request.attempt_ids) > 0)
    if not has_attempt_ids and (not request.start_date or not request.end_date):
        raise MissingFilterError(
            "start_date and end_date are required when using filter-based archive",
        )

    date_from = datetime.fromisoformat(request.start_date) if request.start_date else None
    date_to = datetime.fromisoformat(request.end_date) if request.end_date else None

    with timed("group"):
        await group_attempt_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )

    with timed("db"):
     async with pool.acquire() as conn:
        attempts, _ = await search_attempts(
            conn,
            redis, attempt_ids=request.attempt_ids or None,
            simulation_ids=request.simulation_ids or None,
            profile_ids=request.profile_ids_filter or None,
            cohort_ids=request.cohort_ids or None,
            department_ids=request.department_ids or None,
            scenario_ids=request.scenario_ids or None,
            infinite_mode=request.infinite_mode,
            date_from=date_from,
            date_to=date_to,
            limit=10000,
            offset=0,
        )

        if not attempts:
            return ArchiveAttemptsResponse(
                updated_count=0, profile_ids_to_invalidate=[], idempotency_key=call_id,
            )

        # ── Owner/role scope (BOLA guard) ─────────────────────────────────
        # ``search_attempts`` is filtered only by the caller-supplied ids /
        # filters; it does NOT scope to the actor. Without this, any
        # authenticated profile could archive/unarchive another student's
        # attempts simply by passing their ``attempt_ids``. Mirror the
        # owner-or-strictly-higher-role gate that ``get_attempt_internal``
        # (and ``enforce_attempt_media_access``, issue #148) enforce on the
        # read side: keep only attempts the actor owns or outranks.
        requester = await resolve_profile_identity_context(pool, profile_id, redis)
        # ``attempt_mv.profile_id`` (a.profile_id) is the owner's *resource*
        # profiles_id, so compare against ``requester.profiles_id`` (NOT the
        # artifact profile_id) — exactly as ``get_attempt_internal`` does.
        requester_profiles_id = requester.profiles_id if requester else None
        requester_role = requester.role if requester else None
        attempts = [
            a
            for a in attempts
            if requester_profiles_id is not None
            and check_attempt_access(
                a.profile_id,
                requester_profiles_id,
                request_role=requester_role,
                attempt_role=None,
            )
        ]
        if not attempts:
            return ArchiveAttemptsResponse(
                updated_count=0, profile_ids_to_invalidate=[], idempotency_key=call_id,
            )

        archive_ids: list[UUID] = []
        for attempt in attempts:
            archive_row = await create_attempt_archive(
                conn,
                redis, attempt_id=attempt.attempt_id,
                session_id=session_id,
                archived=request.archived,
                soft=soft,
            )
            archive_ids.append(archive_row.id)

        profile_ids_to_invalidate = list(
            {str(a.profile_id) for a in attempts if a.profile_id}
        )

        if soft and call_id is not None and archive_ids:
            await create_soft_call(
                conn, redis, call_id=call_id, artifact=ARTIFACT, operation=OPERATION,
                artifact_id=archive_ids[0], status="pending",
                patch={
                    "archive_ids": [str(x) for x in archive_ids],
                    "updated_count": len(attempts),
                    "profile_ids": profile_ids_to_invalidate,
                },
            )

    return ArchiveAttemptsResponse(
        updated_count=len(attempts),
        profile_ids_to_invalidate=profile_ids_to_invalidate,
        idempotency_key=call_id,
    )
