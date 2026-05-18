"""Bulk archive/unarchive attempts.

Resolves attempt ids (either explicit list or filter-based search),
writes one archive entry per attempt, and returns the affected
``profile_ids`` so the caller can invalidate the right caches.

Routes/attempt/archive.py is a thin HTTP adapter over
``archive_attempt_impl``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.attempt.group import group_attempt_impl
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_archive.create import create_attempt_archive


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


class ArchiveAttemptsResponse(BaseModel):
    updated_count: int = Field(0, description="Number of attempts updated")
    profile_ids_to_invalidate: list[str] | None = Field(None, description="Profile IDs whose caches need invalidation")


class MissingFilterError(ValueError):
    """Raised when neither attempt_ids nor a date range is provided."""


async def archive_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: ArchiveAttemptsRequest,
) -> ArchiveAttemptsResponse:
    """Bulk archive or unarchive attempts (simulation or benchmark).

    Caller must supply either ``attempt_ids`` or a ``start_date``/``end_date``
    pair; if neither is given, raises ``MissingFilterError`` for the HTTP
    adapter to translate into a 400.
    """
    has_attempt_ids = bool(request.attempt_ids and len(request.attempt_ids) > 0)
    if not has_attempt_ids and (not request.start_date or not request.end_date):
        raise MissingFilterError(
            "start_date and end_date are required when using filter-based archive",
        )

    date_from = datetime.fromisoformat(request.start_date) if request.start_date else None
    date_to = datetime.fromisoformat(request.end_date) if request.end_date else None

    # Resolve group_id (kept on the call path for parity with the rest of
    # the infra; the value isn't used inside this impl today).
    await group_attempt_impl(
        pool, redis,
        profile_id=profile_id,
        session_id=session_id,
        include_history=False,
    )

    async with pool.acquire() as conn:
        attempts, _ = await search_attempts(
            conn,
            attempt_ids=request.attempt_ids or None,
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
                updated_count=0, profile_ids_to_invalidate=[],
            )

        for attempt in attempts:
            await create_attempt_archive(
                conn,
                attempt_id=attempt.attempt_id,
                session_id=session_id,
                archived=request.archived,
            )

    profile_ids_to_invalidate = list(
        {str(a.profile_id) for a in attempts if a.profile_id}
    )

    return ArchiveAttemptsResponse(
        updated_count=len(attempts),
        profile_ids_to_invalidate=profile_ids_to_invalidate,
    )
