"""Tests for infra.websocket.init_run_trackers — combined tracker initialization.

Uses real Redis from testcontainers via redis_client fixture.
"""

import json

import pytest

from app.infra.websocket.init_run_trackers import GENERATION_TTL, init_run_trackers
from app.infra.websocket.run_tracker import WorkUnit


@pytest.mark.asyncio
class TestInitRunTrackers:
    async def test_sets_legacy_keys(self, redis_client):
        """Legacy generation and resource progress keys are set."""
        await init_run_trackers(
            redis_client, run_id="run-123", num_agents=3, num_resources=5
        )

        gen = await redis_client.hgetall("generation:run-123")
        assert gen[b"expected"] == b"3"
        assert gen[b"completed"] == b"0"
        assert gen[b"tool_results"] == b"[]"

        res = await redis_client.hgetall("resource_progress:run-123")
        assert res[b"total"] == b"5"
        assert res[b"completed"] == b"0"

        gen_ttl = await redis_client.ttl("generation:run-123")
        assert gen_ttl > 0 and gen_ttl <= GENERATION_TTL

        res_ttl = await redis_client.ttl("resource_progress:run-123")
        assert res_ttl > 0 and res_ttl <= GENERATION_TTL

    async def test_none_redis_skips_silently(self):
        """When redis is None, does nothing (no error)."""
        await init_run_trackers(None, run_id="run-456", num_agents=1, num_resources=2)

    async def test_single_agent_single_resource(self, redis_client):
        """Minimal case: 1 agent, 1 resource."""
        await init_run_trackers(
            redis_client, run_id="run-min", num_agents=1, num_resources=1
        )

        gen = await redis_client.hgetall("generation:run-min")
        assert gen[b"expected"] == b"1"

        res = await redis_client.hgetall("resource_progress:run-min")
        assert res[b"total"] == b"1"

    async def test_overwrites_existing_keys(self, redis_client):
        """Calling twice overwrites previous values."""
        await init_run_trackers(
            redis_client, run_id="run-ow", num_agents=2, num_resources=3
        )
        await init_run_trackers(
            redis_client, run_id="run-ow", num_agents=5, num_resources=10
        )

        gen = await redis_client.hgetall("generation:run-ow")
        assert gen[b"expected"] == b"5"

        res = await redis_client.hgetall("resource_progress:run-ow")
        assert res[b"total"] == b"10"


@pytest.mark.asyncio
class TestInitRunTrackersWithUnits:
    async def test_sets_both_legacy_and_new_keys(self, redis_client):
        """When units are provided, both legacy and new tracker keys are set."""
        units = [
            WorkUnit(
                agent_id="a1",
                target_type="resource",
                target_name="images",
                modality="image",
            ),
            WorkUnit(agent_id="a2", target_type="entry", target_name="contents"),
        ]
        await init_run_trackers(
            redis_client,
            run_id="run-both",
            num_agents=2,
            num_resources=1,
            units=units,
        )

        # Legacy keys still set
        gen = await redis_client.hgetall("generation:run-both")
        assert gen[b"expected"] == b"2"

        res = await redis_client.hgetall("resource_progress:run-both")
        assert res[b"total"] == b"1"

        # New tracker keys also set
        meta = await redis_client.hgetall("run:run-both:meta")
        assert meta[b"num_agents"] == b"2"

        raw_units = await redis_client.hgetall("run:run-both:units")
        assert len(raw_units) == 2
        img = json.loads(raw_units[b"a1:resource:images"])
        assert img["state"] == "generating"
        assert img["modality"] == "image"

    async def test_no_units_skips_new_tracker(self, redis_client):
        """Without units param, only legacy keys are created."""
        await init_run_trackers(
            redis_client, run_id="run-legacy", num_agents=1, num_resources=1
        )

        # Legacy exists
        gen = await redis_client.hgetall("generation:run-legacy")
        assert gen[b"expected"] == b"1"

        # New tracker does NOT exist
        meta = await redis_client.hgetall("run:run-legacy:meta")
        assert meta == {}
