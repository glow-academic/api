"""Tests for websocket Redis/in-memory helper state."""

import pytest

import app.infra.globals as globals_mod
from app.infra.websocket.add_guest_socket import add_guest_socket
from app.infra.websocket.decrement_guest_count import decrement_guest_count
from app.infra.websocket.get_socket_owner import get_socket_owner
from app.infra.websocket.increment_guest_count import increment_guest_count
from app.infra.websocket.remove_guest_socket import remove_guest_socket
from app.infra.websocket.remove_socket_owner import remove_socket_owner
from app.infra.websocket.set_socket_owner import set_socket_owner


@pytest.fixture
def websocket_state(redis_client):
    """Bind the real test Redis client into the websocket globals."""
    original_redis = globals_mod.redis_client
    globals_mod.redis_client = redis_client
    globals_mod.socket_owner.clear()
    try:
        yield redis_client
    finally:
        globals_mod.redis_client = original_redis
        globals_mod.socket_owner.clear()


class TestGuestSocketHelpers:
    @pytest.mark.asyncio
    async def test_add_and_remove_guest_socket(self, websocket_state):
        await add_guest_socket("sid-1")
        assert await websocket_state.sismember("guest_sockets", "sid-1")

        await remove_guest_socket("sid-1")
        assert not await websocket_state.sismember("guest_sockets", "sid-1")

    @pytest.mark.asyncio
    async def test_guest_socket_helpers_noop_without_redis(self):
        original_redis = globals_mod.redis_client
        globals_mod.redis_client = None
        try:
            await add_guest_socket("sid-2")
            await remove_guest_socket("sid-2")
        finally:
            globals_mod.redis_client = original_redis


class TestGuestCountHelpers:
    @pytest.mark.asyncio
    async def test_increment_and_decrement_guest_count(self, websocket_state):
        assert await increment_guest_count() == 1
        assert await increment_guest_count() == 2
        assert await decrement_guest_count() == 1
        assert await decrement_guest_count() == 0

    @pytest.mark.asyncio
    async def test_decrement_guest_count_floors_at_zero(self, websocket_state):
        await websocket_state.set("guest_connection_count", 0)

        assert await decrement_guest_count() == 0
        raw = await websocket_state.get("guest_connection_count")
        assert raw == b"0"

    @pytest.mark.asyncio
    async def test_guest_count_helpers_return_zero_without_redis(self):
        original_redis = globals_mod.redis_client
        globals_mod.redis_client = None
        try:
            assert await increment_guest_count() == 0
            assert await decrement_guest_count() == 0
        finally:
            globals_mod.redis_client = original_redis


class TestSocketOwnerHelpers:
    @pytest.mark.asyncio
    async def test_set_get_and_remove_socket_owner_in_redis(self, websocket_state):
        await set_socket_owner("profile-1", "sid-1")

        assert await get_socket_owner("profile-1") == "sid-1"
        assert await websocket_state.get("socket_owner:profile-1") == b"sid-1"
        assert await websocket_state.get("socket_to_profile:sid-1") == b"profile-1"

        await remove_socket_owner("profile-1")

        assert await get_socket_owner("profile-1") is None
        assert await websocket_state.get("socket_owner:profile-1") is None
        assert await websocket_state.get("socket_to_profile:sid-1") is None

    @pytest.mark.asyncio
    async def test_socket_owner_helpers_fallback_to_in_memory(self):
        original_redis = globals_mod.redis_client
        globals_mod.redis_client = None
        globals_mod.socket_owner.clear()
        try:
            await set_socket_owner("profile-2", "sid-2")
            assert await get_socket_owner("profile-2") == "sid-2"

            await remove_socket_owner("profile-2")
            assert await get_socket_owner("profile-2") is None
        finally:
            globals_mod.redis_client = original_redis
            globals_mod.socket_owner.clear()
