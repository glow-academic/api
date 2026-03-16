"""Integration tests for infra.runs_context."""

from datetime import UTC, datetime, timedelta

import pytest

from app.infra.runs_context import RunsContext, resolve_runs_context
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


async def test_no_runs_returns_empty(pool, redis_client):
    async with pool.acquire() as conn:
        profile = await create_profile(conn, redis_client)

    result = await resolve_runs_context(pool, profile_id=profile.id)

    assert isinstance(result, RunsContext)
    assert result.items == []
    assert result.total_count == 0


async def test_returns_runs_for_profile(pool, redis_client):
    async with pool.acquire() as conn:
        profile = await create_profile(conn, redis_client)
        session = await create_session(conn, profile_id=profile.id)
        group = await create_group(conn, session_id=session.id)
        run = await create_run(
            conn,
            group_id=group.id,
            session_id=session.id,
            profiles_id=profile.id,
        )
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

    result = await resolve_runs_context(pool, profile_id=profile.id)

    assert result.total_count >= 1
    run_ids = [item.run_id for item in result.items]
    assert run.id in run_ids


async def test_filters_by_group_and_date_range(pool, redis_client):
    async with pool.acquire() as conn:
        profile = await create_profile(conn, redis_client)
        session = await create_session(conn, profile_id=profile.id)
        group = await create_group(conn, session_id=session.id)
        run = await create_run(
            conn,
            group_id=group.id,
            session_id=session.id,
            profiles_id=profile.id,
        )
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

    now = datetime.now(UTC)
    result = await resolve_runs_context(
        pool,
        profile_id=profile.id,
        group_id=group.id,
        date_from=now - timedelta(days=1),
        date_to=now + timedelta(days=1),
    )

    assert result.total_count >= 1
    assert [item.run_id for item in result.items] == [run.id]
