"""Tests for websocket identity lookup helpers (Redis-backed)."""

import pytest

import app.infra.globals as globals_mod
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.is_guest_socket import is_guest_socket


@pytest.fixture
def websocket_identity_runtime(redis_client):
    """Bind real Redis client into globals for the helpers."""
    original_redis = globals_mod.redis_client
    globals_mod.redis_client = redis_client
    try:
        yield redis_client
    finally:
        globals_mod.redis_client = original_redis


class TestIsGuestSocket:
    @pytest.mark.asyncio
    async def test_returns_true_for_guest_socket(self, websocket_identity_runtime):
        await websocket_identity_runtime.sadd("guest_sockets", "sid-1")
        assert await is_guest_socket("sid-1") is True


class TestFindProfileBySocket:
    @pytest.mark.asyncio
    async def test_uses_reverse_index_first(self, websocket_identity_runtime):
        await websocket_identity_runtime.set("socket_to_profile:sid-3", "profile-3")
        assert await find_profile_by_socket("sid-3") == "profile-3"

    @pytest.mark.asyncio
    async def test_falls_back_to_scan_when_reverse_index_missing(
        self, websocket_identity_runtime
    ):
        # Stash a sid in the forward set without writing the reverse index;
        # find_profile_by_socket should still locate it via the bounded
        # SADD set scan fallback.
        await websocket_identity_runtime.sadd(
            "socket_owners:profile-5", "sid-5"
        )
        assert await find_profile_by_socket("sid-5") == "profile-5"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_sid(self, websocket_identity_runtime):
        assert await find_profile_by_socket("sid-nope") is None


class TestFindSessionBySocket:
    @pytest.mark.asyncio
    async def test_returns_session_id_from_redis(self, websocket_identity_runtime):
        await websocket_identity_runtime.set("socket_session:sid-7", "session-7")
        assert await find_session_by_socket("sid-7") == "session-7"
