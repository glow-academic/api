"""Tests for guest count helper."""

import pytest

import app.infra.globals as globals_mod
from app.infra.websocket.get_guest_count import get_guest_count

pytestmark = pytest.mark.asyncio


async def test_get_guest_count_reads_real_redis_value(redis_client):
    original_redis = globals_mod.redis_client
    try:
        globals_mod.redis_client = redis_client
        assert await get_guest_count() == 0

        await redis_client.set("guest_connection_count", 7)

        assert await get_guest_count() == 7
    finally:
        globals_mod.redis_client = original_redis


async def test_get_guest_count_returns_zero_without_redis():
    original_redis = globals_mod.redis_client
    try:
        globals_mod.redis_client = None
        assert await get_guest_count() == 0
    finally:
        globals_mod.redis_client = original_redis
