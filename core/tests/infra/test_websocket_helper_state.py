"""Tests for websocket Redis-backed helper state.

Redis is required — there is no in-memory fallback. Tests bind the real
test Redis client into globals so the helpers route through it.
"""

import pytest

import app.infra.globals as globals_mod
from app.infra.websocket.add_guest_socket import add_guest_socket
from app.infra.websocket.decrement_guest_count import decrement_guest_count
from app.infra.websocket.get_socket_owner import get_socket_owner, get_socket_owners
from app.infra.websocket.increment_guest_count import increment_guest_count
from app.infra.websocket.remove_guest_socket import remove_guest_socket
from app.infra.websocket.remove_socket_owner import remove_socket_owner
from app.infra.websocket.set_socket_owner import set_socket_owner


@pytest.fixture
def websocket_state(redis_client):
    """Bind the real test Redis client into globals for the helpers."""
    original_redis = globals_mod.redis_client
    globals_mod.redis_client = redis_client
    try:
        yield redis_client
    finally:
        globals_mod.redis_client = original_redis


class TestGuestSocketHelpers:
    @pytest.mark.asyncio
    async def test_add_and_remove_guest_socket(self, websocket_state):
        await add_guest_socket("sid-1")
        assert await websocket_state.sismember("guest_sockets", "sid-1")

        await remove_guest_socket("sid-1")
        assert not await websocket_state.sismember("guest_sockets", "sid-1")


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


class TestSocketOwnerHelpers:
    @pytest.mark.asyncio
    async def test_set_get_and_remove_socket_owner_in_redis(self, websocket_state):
        # First socket: set returns True (presence transitions absent → present).
        is_first = await set_socket_owner("profile-1", "sid-1")
        assert is_first is True

        # get_socket_owner is the back-compat shim (returns one arbitrary sid).
        assert await get_socket_owner("profile-1") == "sid-1"
        assert await get_socket_owners("profile-1") == ["sid-1"]
        # SET-backed forward index + reverse index.
        assert await websocket_state.sismember("socket_owners:profile-1", "sid-1")
        assert await websocket_state.get("socket_to_profile:sid-1") == b"profile-1"

        # Second socket on the same profile: NOT first.
        is_first_again = await set_socket_owner("profile-1", "sid-extra")
        assert is_first_again is False
        assert set(await get_socket_owners("profile-1")) == {"sid-1", "sid-extra"}

        # Remove just one — profile still has another socket → not last.
        was_last = await remove_socket_owner("profile-1", "sid-extra")
        assert was_last is False
        assert await get_socket_owners("profile-1") == ["sid-1"]

        # Remove the last → presence transitions present → absent.
        was_last = await remove_socket_owner("profile-1", "sid-1")
        assert was_last is True
        assert await get_socket_owner("profile-1") is None
        assert await websocket_state.smembers("socket_owners:profile-1") == set()
        assert await websocket_state.get("socket_to_profile:sid-1") is None

    @pytest.mark.asyncio
    async def test_remove_socket_owner_wholesale(self, websocket_state):
        await set_socket_owner("profile-9", "sid-a")
        await set_socket_owner("profile-9", "sid-b")
        # No socket_id arg → wholesale removal of the profile's set.
        was_last = await remove_socket_owner("profile-9")
        assert was_last is True
        assert await get_socket_owner("profile-9") is None
        assert await websocket_state.get("socket_to_profile:sid-a") is None
        assert await websocket_state.get("socket_to_profile:sid-b") is None
