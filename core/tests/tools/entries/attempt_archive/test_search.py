"""Tests for search_attempt_archives."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_archive.create import create_attempt_archive
from app.tools.entries.attempt_archive.refresh import refresh_attempt_archive
from app.tools.entries.attempt_archive.search import search_attempt_archives
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    attempt = await create_attempt(
        conn,
        redis_client, call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    result = await create_attempt_archive(
        conn, redis_client, attempt_id=attempt.id, call_id=call.id, archived=True
    )
    return result, attempt


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, attempt = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_archive(conn)

    items = await search_attempt_archives(conn, redis_client, attempt_ids=[attempt.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_attempt_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_archive(conn)

    items = await search_attempt_archives(conn, redis_client, attempt_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    result, attempt = await _setup(conn, redis_client, profile_id)
    await refresh_attempt_archive(conn)

    items = await search_attempt_archives(conn, redis_client, attempt_ids=[attempt.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt_archive(conn)

    items = await search_attempt_archives(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, attempt = await _setup(conn, redis_client, profile_id)

    items = await search_attempt_archives(
        conn, redis_client, attempt_ids=[attempt.id], bypass_mv=True
    )

    ids = [item.id for item in items]
    assert result.id in ids
