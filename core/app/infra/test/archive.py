"""Bulk archive/unarchive benchmark tests.

Creates a group → run → call audit chain, then writes one archive
entry per test id. Returns the count of tests updated.

Soft/accept (stage-inactive, bulk): ``soft=True`` creates all archive rows
dormant (``active=False``) + a pending ``soft_calls_entry`` whose ``patch`` holds
the list of archive ids; the ack ({idempotency_key, accept}) activates them all
(``activate_rows`` with the list) or rejects. Mirrors ``archive_attempt_impl`` so
a benchmark scenario can stage a bulk archive and commit it on accept.
``soft=False`` archives immediately.

Routes/test/archive.py is a thin HTTP adapter over ``archive_test_impl``.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.group.resolve import resolve_group_impl
from app.infra.server_timing import timed
from app.infra.test.types import ArchiveTestsRequest, ArchiveTestsResponse
from app.tools.entries.calls.create import create_call
from app.tools.entries.runs.create import create_run
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.test_archive.create import create_test_archive

ARTIFACT = "test"
OPERATION = "archive"


async def archive_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: ArchiveTestsRequest,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> ArchiveTestsResponse:
    """Archive or unarchive benchmark tests by id, with soft/accept.

    Resolves the caller's test-scoped chat group, opens an audit
    run+call chain on the connection, then writes one archive entry per
    requested test. Cache invalidation lives at the HTTP-adapter layer
    (not part of this contract).
    """
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
                await activate_rows(conn, table="test_archive_entry", ids=archive_ids)
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                operation=OPERATION, artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        return ArchiveTestsResponse(
            updated_count=int(ids.get("updated_count", 0)),
            idempotency_key=idempotency_key,
        )

    with timed("group"):
        group_result = await resolve_group_impl(
            pool, redis,
            artifact_type="test",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )

    with timed("db_write"):
     async with pool.acquire() as conn:
        run_result = await create_run(
            conn, redis, group_id=group_result.group_id, session_id=session_id,
        )
        call_result = await create_call(
            conn, redis, run_id=run_result.id, session_id=session_id,
        )

        archive_ids: list[UUID] = []
        for test_id in request.test_ids:
            archive_row = await create_test_archive(
                conn,
                redis, test_id=test_id,
                call_id=call_result.id,
                archived=request.archived,
                soft=soft,
            )
            archive_ids.append(archive_row.id)

        if soft and call_id is not None and archive_ids:
            await create_soft_call(
                conn, redis, call_id=call_id, artifact=ARTIFACT, operation=OPERATION,
                artifact_id=archive_ids[0], status="pending",
                patch={
                    "archive_ids": [str(x) for x in archive_ids],
                    "updated_count": len(request.test_ids),
                },
            )

    return ArchiveTestsResponse(
        updated_count=len(request.test_ids),
        idempotency_key=call_id,
    )
