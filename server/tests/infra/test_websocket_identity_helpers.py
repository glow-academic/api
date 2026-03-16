"""Tests for websocket identity lookup helpers."""

import pytest

import app.infra.globals as globals_mod
from app.infra.websocket.find_profile_by_socket import (
    _recursion_guard,
    find_profile_by_socket,
)
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.is_guest_socket import is_guest_socket


@pytest.fixture
def websocket_identity_runtime(redis_client):
    """Bind real Redis and clear in-memory ownership state."""
    original_redis = globals_mod.redis_client
    globals_mod.redis_client = redis_client
    globals_mod.socket_owner.clear()
    try:
        yield redis_client
    finally:
        globals_mod.redis_client = original_redis
        globals_mod.socket_owner.clear()


class TestIsGuestSocket:
    @pytest.mark.asyncio
    async def test_returns_true_for_guest_socket(self, websocket_identity_runtime):
        await websocket_identity_runtime.sadd("guest_sockets", "sid-1")
        assert await is_guest_socket("sid-1") is True

    @pytest.mark.asyncio
    async def test_returns_false_without_redis(self):
        original_redis = globals_mod.redis_client
        globals_mod.redis_client = None
        try:
            assert await is_guest_socket("sid-2") is False
        finally:
            globals_mod.redis_client = original_redis


class TestFindProfileBySocket:
    @pytest.mark.asyncio
    async def test_uses_reverse_index_first(self, websocket_identity_runtime):
        await websocket_identity_runtime.set("socket_to_profile:sid-3", "profile-3")
        assert await find_profile_by_socket("sid-3") == "profile-3"

    @pytest.mark.asyncio
    async def test_falls_back_to_in_memory_mapping(self, websocket_identity_runtime):
        globals_mod.socket_owner["profile-4"] = "sid-4"
        assert await find_profile_by_socket("sid-4") == "profile-4"

    @pytest.mark.asyncio
    async def test_falls_back_to_scan_iter_legacy_keys(
        self, websocket_identity_runtime
    ):
        await websocket_identity_runtime.set("socket_owner:profile-5", "sid-5")
        assert await find_profile_by_socket("sid-5") == "profile-5"

    @pytest.mark.asyncio
    async def test_recursion_guard_uses_in_memory_only(self):
        original_redis = globals_mod.redis_client
        globals_mod.redis_client = None
        globals_mod.socket_owner["profile-6"] = "sid-6"
        token = _recursion_guard.set(True)
        try:
            assert await find_profile_by_socket("sid-6") == "profile-6"
        finally:
            _recursion_guard.reset(token)
            globals_mod.socket_owner.clear()
            globals_mod.redis_client = original_redis


class TestFindSessionBySocket:
    @pytest.mark.asyncio
    async def test_returns_session_id_from_redis(self, websocket_identity_runtime):
        await websocket_identity_runtime.set("socket_session:sid-7", "session-7")
        assert await find_session_by_socket("sid-7") == "session-7"

    @pytest.mark.asyncio
    async def test_returns_none_without_redis(self):
        original_redis = globals_mod.redis_client
        globals_mod.redis_client = None
        try:
            assert await find_session_by_socket("sid-8") is None
        finally:
            globals_mod.redis_client = original_redis
