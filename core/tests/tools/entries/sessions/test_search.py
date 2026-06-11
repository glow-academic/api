"""Tests for search_sessions."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.refresh import refresh_sessions
from app.tools.entries.sessions.search import search_sessions

pytestmark = pytest.mark.asyncio


async def test_finds_created_session(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await search_sessions(conn, redis_client, profile_ids=[profile_id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_profile(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await search_sessions(conn, redis_client, profile_ids=[nonexistent_id()])

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_from(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    # date_from in the future — should exclude everything
    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_sessions(conn, redis_client, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    # date_to in the past — should exclude newly created
    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_sessions(conn, redis_client, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_mcp(conn, redis_client, profile_id):
    r_mcp = await create_session(conn, redis_client, profile_id=profile_id, mcp=True)
    r_normal = await create_session(conn, redis_client, profile_id=profile_id, mcp=False)
    await refresh_sessions(conn)

    items = await search_sessions(conn, redis_client, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_pagination_limit(conn, redis_client, profile_id):
    await create_session(conn, redis_client, profile_id=profile_id)
    await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await search_sessions(
        conn,
        redis_client, profile_ids=[profile_id],
        limit=1,
    )

    assert len(items) == 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await search_sessions(conn, redis_client)

    assert len(items) >= 1


async def test_pagination_tied_created_at_deterministic(conn, redis_client, profile_id):
    """P2: sessions with an IDENTICAL ``session_created_at`` must paginate
    without dup/skip and deterministically across calls.

    ``ORDER BY session_created_at DESC`` (and the Python merge-sort) is
    non-unique; without the ``session_id`` tiebreaker, tied timestamps order
    arbitrarily and a session can dup/skip across page boundaries. All six
    sessions share one timestamp → the order is decided purely by the
    ``session_id`` tiebreaker."""
    tied_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    created = []
    for _ in range(6):
        r = await create_session(
            conn, redis_client, profile_id=profile_id, created_at=tied_ts,
        )
        created.append(str(r.id))
    await refresh_sessions(conn)

    async def _page(off):
        items = await search_sessions(
            conn, redis_client, profile_ids=[profile_id],
            limit=2, offset=off, bypass_cache=True,
        )
        return [str(i.id) for i in items]

    # Deterministic: same offset twice → identical result.
    assert await _page(0) == await _page(0)
    assert await _page(2) == await _page(2)

    # Full walk: every session exactly once, no dup/skip across pages.
    flat = (await _page(0)) + (await _page(2)) + (await _page(4))
    assert set(flat) == set(created)
    assert len(set(flat)) == 6


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)

    items = await search_sessions(
        conn,
        redis_client, profile_ids=[profile_id],
        bypass_mv=True,
    )

    ids = [item.id for item in items]
    assert result.id in ids
