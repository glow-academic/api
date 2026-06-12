"""Tests for create_video_completion."""

import pytest

from app.tools.entries.video_completion.create import create_video_completion
from app.tools.entries.video_completion.refresh import refresh_video_completion
from app.tools.entries.video_completion.refresh import MV_NAME
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.videos.create import create_video

pytestmark = pytest.mark.asyncio


async def _setup_entry(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    seed = await create_video(conn, redis_client, session_id=session.id)
    return session, call, seed


async def test_create_returns_id(conn, redis_client, profile_id):
    session, call, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_video_completion(conn, redis_client, video_id=seed.id, session_id=session.id)

    assert result.id is not None


async def test_row_not_visible_before_refresh(conn, redis_client, profile_id):
    session, call, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_video_completion(conn, redis_client, video_id=seed.id, session_id=session.id)

    row = await conn.fetchrow(f"SELECT id FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is None


async def test_refresh_exposes_created_row(conn, redis_client, profile_id):
    session, call, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_video_completion(conn, redis_client, video_id=seed.id, session_id=session.id, mcp=True)
    await refresh_video_completion(conn)

    row = await conn.fetchrow(f"SELECT id, mcp FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is not None
    assert row['id'] == result.id
    assert row['mcp'] is True


async def test_duplicate_completion_is_idempotent(conn, redis_client, profile_id):
    """C1-B: a duplicate hard completion must NOT append a second active row."""
    session, call, seed = await _setup_entry(conn, redis_client, profile_id)

    first = await create_video_completion(conn, redis_client, video_id=seed.id, session_id=session.id)
    second = await create_video_completion(conn, redis_client, video_id=seed.id, session_id=session.id)

    rows = await conn.fetch(
        "SELECT id, active FROM video_completion_entry WHERE video_id = $1", seed.id
    )
    assert len(rows) == 1
    assert rows[0]["active"] is True
    assert first.id == second.id


async def test_hard_completion_supersedes_dormant_soft(conn, redis_client, profile_id):
    """C1-B: a hard completion promotes a dormant soft proposal in place."""
    session, call, seed = await _setup_entry(conn, redis_client, profile_id)

    soft = await create_video_completion(conn, redis_client, video_id=seed.id, session_id=session.id, soft=True)
    assert soft.active is False

    hard = await create_video_completion(conn, redis_client, video_id=seed.id, session_id=session.id)

    rows = await conn.fetch(
        "SELECT id, active FROM video_completion_entry WHERE video_id = $1", seed.id
    )
    assert len(rows) == 1
    assert rows[0]["active"] is True
    assert hard.id == soft.id
    assert hard.active is True
