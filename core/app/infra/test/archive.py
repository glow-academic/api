"""Bulk archive/unarchive benchmark tests.

Creates a group → run → call audit chain, then writes one archive
entry per test id. Returns the count of tests updated.

Routes/test/archive.py is a thin HTTP adapter over ``archive_test_impl``.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.group.resolve import resolve_group_impl
from app.infra.test.types import ArchiveTestsRequest, ArchiveTestsResponse
from app.tools.entries.calls.create import create_call
from app.tools.entries.runs.create import create_run
from app.tools.entries.test_archive.create import create_test_archive


async def archive_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: ArchiveTestsRequest,
) -> ArchiveTestsResponse:
    """Archive or unarchive benchmark tests by id.

    Resolves the caller's test-scoped chat group, opens an audit
    run+call chain on the connection, then writes one archive entry per
    requested test. Cache invalidation lives at the HTTP-adapter layer
    (not part of this contract).
    """
    group_result = await resolve_group_impl(
        pool, redis,
        artifact_type="test",
        profile_id=profile_id,
        session_id=session_id,
        include_history=False,
    )

    async with pool.acquire() as conn:
        run_result = await create_run(
            conn, redis, group_id=group_result.group_id, session_id=session_id,
        )
        call_result = await create_call(
            conn, redis, run_id=run_result.id, session_id=session_id,
        )

        updated_count = 0
        for test_id in request.test_ids:
            await create_test_archive(
                conn,
                redis, test_id=test_id,
                call_id=call_result.id,
                archived=request.archived,
            )
            updated_count += 1

    return ArchiveTestsResponse(updated_count=updated_count)
