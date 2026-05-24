"""Tests for stream session management — Redis-backed sid lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.infra.stream.session import (
    create_session,
    destroy_session,
    get_joined_entities,
    get_session_profile,
    is_entity_joined,
    join_entity,
    leave_entity,
)

pytestmark = pytest.mark.asyncio


def _make_mock_redis():
    """Create a mock Redis client with basic KV + set ops."""
    store = {}
    sets = {}

    mock = AsyncMock()

    async def fake_setex(key, ttl, data):
        store[key] = data

    async def fake_get(key):
        return store.get(key)

    async def fake_delete(*keys):
        for k in keys:
            store.pop(k, None)
            sets.pop(k, None)

    async def fake_sadd(key, member):
        sets.setdefault(key, set()).add(member)

    async def fake_srem(key, member):
        if key in sets:
            sets[key].discard(member)

    async def fake_smembers(key):
        return sets.get(key, set())

    async def fake_sismember(key, member):
        return member in sets.get(key, set())

    async def fake_expire(key, ttl):
        pass

    mock.setex = fake_setex
    mock.get = fake_get
    mock.delete = fake_delete
    mock.sadd = fake_sadd
    mock.srem = fake_srem
    mock.smembers = fake_smembers
    mock.sismember = fake_sismember
    mock.expire = fake_expire

    return mock


async def test_create_session_returns_sid():
    """create_session returns a non-empty string sid."""
    mock_redis = _make_mock_redis()
    profile_id = uuid4()

    with patch("app.infra.stream.session.get_redis_client", return_value=mock_redis):
        sid = await create_session(profile_id)

    assert isinstance(sid, str)
    assert len(sid) > 0


async def test_create_and_get_session_profile_roundtrip():
    """Created session profile can be retrieved."""
    mock_redis = _make_mock_redis()
    profile_id = uuid4()

    with patch("app.infra.stream.session.get_redis_client", return_value=mock_redis):
        sid = await create_session(profile_id)
        resolved = await get_session_profile(sid)

    assert resolved == profile_id


async def test_get_session_profile_returns_none_for_unknown_sid():
    """get_session_profile returns None for non-existent sid."""
    mock_redis = _make_mock_redis()

    with patch("app.infra.stream.session.get_redis_client", return_value=mock_redis):
        result = await get_session_profile("nonexistent-sid")

    assert result is None


async def test_destroy_session_removes_data():
    """destroy_session cleans up profile and entities keys."""
    mock_redis = _make_mock_redis()
    profile_id = uuid4()

    with patch("app.infra.stream.session.get_redis_client", return_value=mock_redis):
        sid = await create_session(profile_id)
        entity_id = uuid4()
        await join_entity(sid, "simulation", entity_id)
        await destroy_session(sid)

        # Profile should be gone
        assert await get_session_profile(sid) is None
        # Entities should be gone
        assert await get_joined_entities(sid) == set()


async def test_join_and_leave_entity():
    """join_entity adds to set; leave_entity removes."""
    mock_redis = _make_mock_redis()
    profile_id = uuid4()
    entity_id = uuid4()

    with patch("app.infra.stream.session.get_redis_client", return_value=mock_redis):
        sid = await create_session(profile_id)

        await join_entity(sid, "cohort", entity_id)
        entities = await get_joined_entities(sid)
        assert f"cohort:{entity_id}" in entities

        await leave_entity(sid, "cohort", entity_id)
        entities = await get_joined_entities(sid)
        assert f"cohort:{entity_id}" not in entities


async def test_is_entity_joined():
    """is_entity_joined returns True after join, False after leave."""
    mock_redis = _make_mock_redis()
    profile_id = uuid4()
    entity_id = uuid4()

    with patch("app.infra.stream.session.get_redis_client", return_value=mock_redis):
        sid = await create_session(profile_id)

        assert await is_entity_joined(sid, "persona", entity_id) is False

        await join_entity(sid, "persona", entity_id)
        assert await is_entity_joined(sid, "persona", entity_id) is True


async def test_multiple_entities_in_session():
    """Multiple entities can be joined to the same session."""
    mock_redis = _make_mock_redis()
    profile_id = uuid4()
    e1 = uuid4()
    e2 = uuid4()

    with patch("app.infra.stream.session.get_redis_client", return_value=mock_redis):
        sid = await create_session(profile_id)

        await join_entity(sid, "cohort", e1)
        await join_entity(sid, "simulation", e2)

        entities = await get_joined_entities(sid)
        assert f"cohort:{e1}" in entities
        assert f"simulation:{e2}" in entities
        assert len(entities) == 2
