"""Tests for low-level websocket state helpers."""

import pytest

from app.infra.websocket.get_active_connection import get_active_connection
from app.infra.websocket.get_active_run import get_active_run
from app.infra.websocket.get_socket_owner import get_socket_owner
from app.infra.websocket.remove_active_connection import remove_active_connection
from app.infra.websocket.remove_active_run import remove_active_run
from app.infra.websocket.remove_socket_owner import remove_socket_owner
from app.infra.websocket.set_active_connection import set_active_connection
from app.infra.websocket.set_active_run import set_active_run
from app.infra.websocket.set_socket_owner import set_socket_owner

pytestmark = pytest.mark.asyncio


async def test_socket_owner_round_trip_with_real_redis(redis_client):
    await set_socket_owner("profile-1", "sid-1", redis_client=redis_client)

    assert await get_socket_owner("profile-1", redis_client=redis_client) == "sid-1"
    assert await redis_client.get("socket_to_profile:sid-1") == b"profile-1"

    await remove_socket_owner("profile-1", redis_client=redis_client)

    assert await get_socket_owner("profile-1", redis_client=redis_client) is None
    assert await redis_client.get("socket_to_profile:sid-1") is None


async def test_socket_owner_falls_back_to_supplied_in_memory_store():
    owners: dict[str, str] = {}

    await set_socket_owner("profile-2", "sid-2", socket_owner=owners)
    assert await get_socket_owner("profile-2", socket_owner=owners) == "sid-2"

    await remove_socket_owner("profile-2", socket_owner=owners)
    assert owners == {}


async def test_active_run_round_trip_with_real_redis(redis_client):
    await set_active_run("chat-1", "run-1", redis_client=redis_client)

    assert await get_active_run("chat-1", redis_client=redis_client) == "run-1"

    await remove_active_run("chat-1", redis_client=redis_client)

    assert await get_active_run("chat-1", redis_client=redis_client) is None


async def test_active_connection_adds_and_removes_members(redis_client):
    await set_active_connection("chat-2", "sid-a", redis_client=redis_client)
    await set_active_connection("chat-2", "sid-b", redis_client=redis_client)

    active = await get_active_connection("chat-2", redis_client=redis_client)
    assert active in {"sid-a", "sid-b"}

    await remove_active_connection("chat-2", "sid-a", redis_client=redis_client)
    remaining = await redis_client.smembers("active_connection:chat-2")
    assert remaining == {b"sid-b"}

    await remove_active_connection("chat-2", "sid-b", redis_client=redis_client)
    assert await redis_client.exists("active_connection:chat-2") == 0
