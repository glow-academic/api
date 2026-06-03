"""Tests for socket identity store/resolve/remove via Redis."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.infra.identity.resolve_identity import Identity
from app.infra.identity.socket import (
    _IDENTITY_TTL,
    remove_socket_identity,
    resolve_socket_identity,
    store_socket_identity,
)

pytestmark = pytest.mark.asyncio


def _make_identity(**overrides):
    defaults = dict(
        profile_id=uuid4(),
        session_id=uuid4(),
        email="test@example.com",
        role="admin",
        is_emulation=False,
        actor_profile_id=None,
        emulation_depth=0,
        is_mcp=False,
    )
    defaults.update(overrides)
    return Identity(**defaults)


async def test_store_and_resolve_roundtrip():
    """Storing an identity and resolving it returns equivalent data."""
    identity = _make_identity()
    sid = f"test-sid-{uuid4().hex[:8]}"

    mock_redis = AsyncMock()
    stored_data = {}

    async def fake_setex(key, ttl, data):
        stored_data[key] = data

    async def fake_get(key):
        return stored_data.get(key)

    mock_redis.setex = fake_setex
    mock_redis.get = fake_get

    with patch("app.infra.identity.socket.get_redis_client", return_value=mock_redis):
        await store_socket_identity(sid, identity)
        result = await resolve_socket_identity(sid)

    assert result is not None
    assert result.profile_id == identity.profile_id
    assert result.session_id == identity.session_id
    assert result.email == identity.email
    assert result.role == identity.role
    assert result.is_emulation == identity.is_emulation
    assert result.is_mcp == identity.is_mcp


async def test_store_sets_correct_redis_key_and_ttl():
    """store_socket_identity uses the expected key pattern and TTL."""
    identity = _make_identity()
    sid = "my-sid-42"

    mock_redis = AsyncMock()
    calls = []

    async def fake_setex(key, ttl, data):
        calls.append((key, ttl, data))

    mock_redis.setex = fake_setex

    with patch("app.infra.identity.socket.get_redis_client", return_value=mock_redis):
        await store_socket_identity(sid, identity)

    assert len(calls) == 1
    key, ttl, data = calls[0]
    assert key == f"socket_identity:{sid}"
    assert ttl == _IDENTITY_TTL
    parsed = json.loads(data)
    assert parsed["profile_id"] == str(identity.profile_id)


async def test_resolve_returns_none_when_no_data():
    """resolve_socket_identity returns None for unknown sid."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch("app.infra.identity.socket.get_redis_client", return_value=mock_redis):
        result = await resolve_socket_identity("nonexistent-sid")

    assert result is None


async def test_remove_deletes_redis_key():
    """remove_socket_identity deletes the correct Redis key."""
    sid = "rm-sid-99"
    mock_redis = AsyncMock()
    deleted_keys = []

    async def fake_delete(*keys):
        deleted_keys.extend(keys)

    mock_redis.delete = fake_delete

    with patch("app.infra.identity.socket.get_redis_client", return_value=mock_redis):
        await remove_socket_identity(sid)

    assert f"socket_identity:{sid}" in deleted_keys


async def test_store_with_emulation_identity():
    """An emulation identity roundtrips with actor_profile_id."""
    actor_pid = uuid4()
    identity = _make_identity(
        is_emulation=True,
        actor_profile_id=actor_pid,
        emulation_depth=2,
    )
    sid = f"emu-sid-{uuid4().hex[:8]}"

    mock_redis = AsyncMock()
    stored = {}

    async def fake_setex(key, ttl, data):
        stored[key] = data

    async def fake_get(key):
        return stored.get(key)

    mock_redis.setex = fake_setex
    mock_redis.get = fake_get

    with patch("app.infra.identity.socket.get_redis_client", return_value=mock_redis):
        await store_socket_identity(sid, identity)
        result = await resolve_socket_identity(sid)

    assert result is not None
    assert result.is_emulation is True
    assert result.actor_profile_id == actor_pid
    assert result.emulation_depth == 2


async def test_store_propagates_when_redis_unavailable():
    """Redis is REQUIRED: when it is uninitialized, get_redis_client() raises
    RuntimeError and store_socket_identity surfaces it (no silent no-op)."""
    with patch(
        "app.infra.identity.socket.get_redis_client",
        side_effect=RuntimeError("Redis client not initialized"),
    ):
        with pytest.raises(RuntimeError, match="Redis client not initialized"):
            await store_socket_identity("sid", _make_identity())


async def test_resolve_propagates_when_redis_unavailable():
    """resolve_socket_identity surfaces the RuntimeError raised by
    get_redis_client when Redis is uninitialized (no silent None)."""
    with patch(
        "app.infra.identity.socket.get_redis_client",
        side_effect=RuntimeError("Redis client not initialized"),
    ):
        with pytest.raises(RuntimeError, match="Redis client not initialized"):
            await resolve_socket_identity("sid")
