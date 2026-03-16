"""Tests for infra.websocket.run_tracker — work-unit state machine.

Uses real Redis from testcontainers via redis_client fixture.
"""

import json

import pytest

from app.infra.websocket.run_tracker import (
    RUN_TTL,
    WorkUnit,
    cleanup_run,
    fail_unit,
    get_run_status,
    init_run,
    promote_unit,
    record_agent_done,
    record_unit_soft,
)


def _unit(
    agent: str = "a1",
    ttype: str = "resource",
    name: str = "images",
    modality: str | None = None,
) -> WorkUnit:
    return WorkUnit(
        agent_id=agent, target_type=ttype, target_name=name, modality=modality
    )


@pytest.mark.asyncio
class TestInitRun:
    async def test_registers_units_in_redis(self, redis_client):
        units = [
            _unit("a1", "resource", "images", "image"),
            _unit("a1", "resource", "texts"),
            _unit("a2", "entry", "contents"),
        ]
        await init_run(redis_client, run_id="r1", units=units)

        # Meta key
        meta = await redis_client.hgetall("run:r1:meta")
        assert meta[b"num_agents"] == b"2"
        assert meta[b"completed_agents"] == b"0"
        assert json.loads(meta[b"tool_results"]) == []

        # Units key
        raw_units = await redis_client.hgetall("run:r1:units")
        assert len(raw_units) == 3

        img = json.loads(raw_units[b"a1:resource:images"])
        assert img["state"] == "generating"
        assert img["modality"] == "image"

        contents = json.loads(raw_units[b"a2:entry:contents"])
        assert contents["state"] == "generating"
        assert contents["modality"] is None

    async def test_sets_ttl(self, redis_client):
        await init_run(redis_client, run_id="r-ttl", units=[_unit()])

        meta_ttl = await redis_client.ttl("run:r-ttl:meta")
        units_ttl = await redis_client.ttl("run:r-ttl:units")
        assert 0 < meta_ttl <= RUN_TTL
        assert 0 < units_ttl <= RUN_TTL

    async def test_explicit_num_agents(self, redis_client):
        """num_agents can be overridden (e.g. when agents share units)."""
        await init_run(
            redis_client, run_id="r-na", units=[_unit("a1"), _unit("a2")], num_agents=5
        )
        meta = await redis_client.hgetall("run:r-na:meta")
        assert meta[b"num_agents"] == b"5"

    async def test_none_redis_skips(self):
        await init_run(None, run_id="r-none", units=[_unit()])

    async def test_overwrites_on_reinit(self, redis_client):
        await init_run(redis_client, run_id="r-ow", units=[_unit("a1")])
        await init_run(
            redis_client,
            run_id="r-ow",
            units=[_unit("a1"), _unit("a2"), _unit("a3")],
        )
        raw = await redis_client.hgetall("run:r-ow:units")
        assert len(raw) == 3


@pytest.mark.asyncio
class TestRecordUnitSoft:
    async def test_transitions_to_soft(self, redis_client):
        await init_run(
            redis_client, run_id="rs1", units=[_unit("a1", "resource", "images")]
        )

        completed, total = await record_unit_soft(
            redis_client,
            run_id="rs1",
            agent_id="a1",
            target_type="resource",
            target_name="images",
            result_id="res-123",
            modality="image",
        )
        assert completed == 1
        assert total == 1

        raw = await redis_client.hget("run:rs1:units", "a1:resource:images")
        data = json.loads(raw)
        assert data["state"] == "soft"
        assert data["result_id"] == "res-123"
        assert data["modality"] == "image"

    async def test_partial_progress(self, redis_client):
        units = [_unit("a1", "resource", "images"), _unit("a1", "resource", "texts")]
        await init_run(redis_client, run_id="rs2", units=units)

        completed, total = await record_unit_soft(
            redis_client,
            run_id="rs2",
            agent_id="a1",
            target_type="resource",
            target_name="images",
            result_id="r1",
        )
        assert completed == 1
        assert total == 2

    async def test_stores_metadata(self, redis_client):
        await init_run(redis_client, run_id="rs3", units=[_unit()])

        await record_unit_soft(
            redis_client,
            run_id="rs3",
            agent_id="a1",
            target_type="resource",
            target_name="images",
            metadata={"tokens": 500},
        )

        raw = await redis_client.hget("run:rs3:units", "a1:resource:images")
        data = json.loads(raw)
        assert data["metadata"]["tokens"] == 500


@pytest.mark.asyncio
class TestPromoteUnit:
    async def test_soft_to_active(self, redis_client):
        await init_run(redis_client, run_id="rp1", units=[_unit()])

        await record_unit_soft(
            redis_client,
            run_id="rp1",
            agent_id="a1",
            target_type="resource",
            target_name="images",
            result_id="r1",
        )
        await promote_unit(
            redis_client,
            run_id="rp1",
            agent_id="a1",
            target_type="resource",
            target_name="images",
        )

        raw = await redis_client.hget("run:rp1:units", "a1:resource:images")
        assert json.loads(raw)["state"] == "active"

    async def test_noop_if_missing(self, redis_client):
        """Promoting a non-existent unit does nothing."""
        await init_run(redis_client, run_id="rp2", units=[_unit()])
        await promote_unit(
            redis_client,
            run_id="rp2",
            agent_id="a1",
            target_type="resource",
            target_name="nonexistent",
        )


@pytest.mark.asyncio
class TestFailUnit:
    async def test_transitions_to_failed(self, redis_client):
        await init_run(redis_client, run_id="rf1", units=[_unit()])

        await fail_unit(
            redis_client,
            run_id="rf1",
            agent_id="a1",
            target_type="resource",
            target_name="images",
        )

        raw = await redis_client.hget("run:rf1:units", "a1:resource:images")
        assert json.loads(raw)["state"] == "failed"

    async def test_fail_after_soft(self, redis_client):
        """Can fail a unit that was already soft (resolution loser)."""
        await init_run(redis_client, run_id="rf2", units=[_unit()])
        await record_unit_soft(
            redis_client,
            run_id="rf2",
            agent_id="a1",
            target_type="resource",
            target_name="images",
            result_id="r1",
        )
        await fail_unit(
            redis_client,
            run_id="rf2",
            agent_id="a1",
            target_type="resource",
            target_name="images",
        )

        raw = await redis_client.hget("run:rf2:units", "a1:resource:images")
        assert json.loads(raw)["state"] == "failed"


@pytest.mark.asyncio
class TestMultiAgentCompetition:
    async def test_three_agents_same_resource(self, redis_client):
        """3 agents compete on images — all go soft, one promoted, two failed."""
        units = [
            _unit("a1", "resource", "images", "image"),
            _unit("a2", "resource", "images", "image"),
            _unit("a3", "resource", "images", "image"),
        ]
        await init_run(redis_client, run_id="rc1", units=units, num_agents=3)

        # All complete → soft
        for agent in ["a1", "a2", "a3"]:
            await record_unit_soft(
                redis_client,
                run_id="rc1",
                agent_id=agent,
                target_type="resource",
                target_name="images",
                result_id=f"res-{agent}",
            )

        status = await get_run_status(redis_client, run_id="rc1")
        assert status.soft == 3
        assert status.generating == 0

        # Promote a2, fail a1 and a3
        await promote_unit(
            redis_client,
            run_id="rc1",
            agent_id="a2",
            target_type="resource",
            target_name="images",
        )
        await fail_unit(
            redis_client,
            run_id="rc1",
            agent_id="a1",
            target_type="resource",
            target_name="images",
        )
        await fail_unit(
            redis_client,
            run_id="rc1",
            agent_id="a3",
            target_type="resource",
            target_name="images",
        )

        status = await get_run_status(redis_client, run_id="rc1")
        assert status.active == 1
        assert status.failed == 2
        assert status.soft == 0


@pytest.mark.asyncio
class TestRecordAgentDone:
    async def test_returns_all_done_when_all_agents_finish(self, redis_client):
        await init_run(
            redis_client,
            run_id="rad1",
            units=[_unit("a1"), _unit("a2")],
            num_agents=2,
        )

        done, results = await record_agent_done(
            redis_client,
            run_id="rad1",
            tool_results=[{"resource_type": "images"}],
        )
        assert done is False
        assert len(results) == 1

        done, results = await record_agent_done(
            redis_client,
            run_id="rad1",
            tool_results=[{"resource_type": "texts"}],
        )
        assert done is True
        assert len(results) == 2

    async def test_accumulates_tool_results(self, redis_client):
        await init_run(
            redis_client,
            run_id="rad2",
            units=[_unit("a1"), _unit("a2"), _unit("a3")],
            num_agents=3,
        )

        for i in range(3):
            _, results = await record_agent_done(
                redis_client,
                run_id="rad2",
                tool_results=[{"id": i}],
            )

        assert len(results) == 3
        assert {r["id"] for r in results} == {0, 1, 2}


@pytest.mark.asyncio
class TestGetRunStatus:
    async def test_returns_correct_counts(self, redis_client):
        units = [
            _unit("a1", "resource", "images"),
            _unit("a1", "entry", "contents"),
            _unit("a2", "resource", "texts"),
        ]
        await init_run(redis_client, run_id="rgs1", units=units, num_agents=2)

        await record_unit_soft(
            redis_client,
            run_id="rgs1",
            agent_id="a1",
            target_type="resource",
            target_name="images",
        )
        await record_agent_done(
            redis_client,
            run_id="rgs1",
            tool_results=[{"x": 1}],
        )

        status = await get_run_status(redis_client, run_id="rgs1")
        assert status.total_units == 3
        assert status.generating == 2
        assert status.soft == 1
        assert status.num_agents == 2
        assert status.completed_agents == 1
        assert status.all_agents_done is False

    async def test_empty_run(self, redis_client):
        status = await get_run_status(redis_client, run_id="nonexistent")
        assert status.total_units == 0
        assert status.all_agents_done is True


@pytest.mark.asyncio
class TestCleanupRun:
    async def test_removes_all_keys(self, redis_client):
        await init_run(redis_client, run_id="rcl1", units=[_unit()])
        await cleanup_run(redis_client, run_id="rcl1")

        assert await redis_client.exists("run:rcl1:meta") == 0
        assert await redis_client.exists("run:rcl1:units") == 0

    async def test_none_redis_no_error(self):
        await cleanup_run(None, run_id="rcl2")


@pytest.mark.asyncio
class TestFallback:
    """In-memory fallback when redis is None."""

    async def test_full_lifecycle_without_redis(self):
        from app.infra.websocket.run_tracker import _fallback

        run_id = "fb1"
        units = [_unit("a1", "resource", "images"), _unit("a2", "entry", "contents")]

        await init_run(None, run_id=run_id, units=units)

        # Unit soft
        completed, total = await record_unit_soft(
            None,
            run_id=run_id,
            agent_id="a1",
            target_type="resource",
            target_name="images",
            result_id="r1",
        )
        assert completed == 1
        assert total == 2

        # Promote
        await promote_unit(
            None,
            run_id=run_id,
            agent_id="a1",
            target_type="resource",
            target_name="images",
        )

        # Agent done
        done, _ = await record_agent_done(None, run_id=run_id, tool_results=[])
        assert done is False

        done, results = await record_agent_done(
            None,
            run_id=run_id,
            tool_results=[{"x": 1}],
        )
        assert done is True
        assert len(results) == 1

        # Status
        status = await get_run_status(None, run_id=run_id)
        assert status.total_units == 2
        assert status.active == 1
        assert status.all_agents_done is True

        # Cleanup
        await cleanup_run(None, run_id=run_id)
        assert f"run:{run_id}:meta" not in _fallback
        assert f"run:{run_id}:units" not in _fallback
