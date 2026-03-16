"""Tests for generation tracker helper."""

import pytest

import app.infra.globals as globals_mod
from app.infra.websocket.generation_tracker import (
    cleanup_generation,
    init_generation,
    init_resource_progress,
    record_agent_complete,
    record_resource_complete,
)

pytestmark = pytest.mark.asyncio


async def test_generation_tracker_round_trip_with_real_redis(redis_client):
    original_redis = globals_mod.redis_client
    try:
        globals_mod.redis_client = redis_client

        await init_generation("run-1", expected_agent_count=2)
        done, results = await record_agent_complete("run-1", [{"tool": "a"}])
        assert done is False
        assert results == [{"tool": "a"}]

        done, results = await record_agent_complete("run-1", [{"tool": "b"}])
        assert done is True
        assert results == [{"tool": "a"}, {"tool": "b"}]

        await init_resource_progress("run-1", total_resources=3)
        assert await record_resource_complete("run-1", "documents") == (1, 3)
        assert await record_resource_complete("run-1", "images") == (2, 3)

        await cleanup_generation("run-1")
        assert await redis_client.exists("generation:run-1") == 0
        assert await redis_client.exists("resource_progress:run-1") == 0
    finally:
        globals_mod.redis_client = original_redis


async def test_generation_tracker_falls_back_without_redis():
    original_redis = globals_mod.redis_client
    try:
        globals_mod.redis_client = None

        await init_generation("run-fallback", expected_agent_count=1)
        done, results = await record_agent_complete("run-fallback", [{"tool": "x"}])
        assert done is True
        assert results == [{"tool": "x"}]

        await init_resource_progress("run-fallback", total_resources=2)
        assert await record_resource_complete("run-fallback", "documents") == (1, 2)

        await cleanup_generation("run-fallback")
    finally:
        globals_mod.redis_client = original_redis
