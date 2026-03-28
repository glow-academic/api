from __future__ import annotations

from uuid import uuid4

import pytest

from app.infra.sessions.get import get_session_impl
from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.refresh import refresh_sessions
from app.tools.resources.profiles.create import create_profile


pytestmark = pytest.mark.asyncio


async def test_get_session_impl_returns_latest_active_session(pool, redis_client):
    async with pool.acquire() as conn:
        profile = await create_profile(conn, redis_client)
        older = await create_session(conn, profile_id=profile.id)
        newer = await create_session(conn, profile_id=profile.id)
        await conn.execute(
            "UPDATE sessions_entry SET created_at = NOW() - interval '2 days' WHERE id = $1",
            older.id,
        )
        await refresh_sessions(conn)

    async with pool.acquire() as conn:
        session_id = await get_session_impl(
            conn,
            profile.id,
            redis=redis_client,
            bypass_cache=True,
        )

    assert session_id == newer.id


async def test_get_session_impl_returns_none_when_profile_has_no_sessions(
    pool,
    redis_client,
):
    async with pool.acquire() as conn:
        session_id = await get_session_impl(
            conn,
            uuid4(),
            redis=redis_client,
            bypass_cache=True,
        )

    assert session_id is None


async def test_get_session_impl_reads_from_cache_after_first_lookup(
    pool,
    redis_client,
):
    async with pool.acquire() as conn:
        profile = await create_profile(conn, redis_client)
        session = await create_session(conn, profile_id=profile.id)
        await refresh_sessions(conn)
        cached = await get_session_impl(
            conn,
            profile.id,
            redis=redis_client,
            bypass_cache=False,
        )
        assert cached == session.id

        await conn.execute("DELETE FROM sessions_entry WHERE id = $1", session.id)

        cached_again = await get_session_impl(
            conn,
            profile.id,
            redis=redis_client,
            bypass_cache=False,
        )

    assert cached_again == session.id
