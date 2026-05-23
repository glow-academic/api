"""Tests for search_attempts."""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt.refresh import refresh_attempt
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.sessions.create import create_session
from app.tools.resources.profiles.create import create_profile
from app.tools.resources.roles.create import create_role
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    persona = await create_persona(conn, redis_client)
    attempt = await create_attempt(
        conn,
        redis_client, session_id=session.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    return attempt


async def test_finds_created_entry(conn, redis_client, profile_id):
    attempt = await _setup(conn, redis_client, profile_id)
    await refresh_attempt(conn)

    items, _total_count = await search_attempts(conn, redis_client)

    ids = [item.attempt_id for item in items]
    assert attempt.id in ids


async def test_filters_by_profile_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt(conn)

    items, _total_count = await search_attempts(conn, redis_client, profile_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_role_id(conn, redis_client):
    role = await create_role(conn, redis_client, name=f"attempt-role-{nonexistent_id()}")
    profile = await create_profile(conn, redis_client, role_id=role.id)
    attempt = await _setup(conn, redis_client, profile.id)
    await refresh_attempt(conn)

    items, _total_count = await search_attempts(conn, redis_client, role_ids=[role.id])

    ids = [item.attempt_id for item in items]
    assert attempt.id in ids


async def test_filters_by_missing_role_id(conn, redis_client):
    role = await create_role(conn, redis_client, name=f"attempt-role-{nonexistent_id()}")
    profile = await create_profile(conn, redis_client, role_id=role.id)
    await _setup(conn, redis_client, profile.id)
    await refresh_attempt(conn)

    items, _total_count = await search_attempts(conn, redis_client, role_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt(conn)

    items, _total_count = await search_attempts(conn, redis_client, limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await refresh_attempt(conn)

    items, _total_count = await search_attempts(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    attempt = await _setup(conn, redis_client, profile_id)

    items, _total_count = await search_attempts(conn, redis_client, bypass_mv=True)

    ids = [item.attempt_id for item in items]
    assert attempt.id in ids
