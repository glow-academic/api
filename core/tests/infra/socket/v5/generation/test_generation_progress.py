"""Tests for generation_progress_impl using real Redis-backed trackers."""

from __future__ import annotations

import pytest

import app.infra.globals as globals_mod
from app.infra.websocket.generation_progress_impl import generation_progress_impl
from app.infra.websocket.init_run_trackers import init_run_trackers
from app.infra.websocket.run_tracker import WorkUnit
from app.infra.websocket.socket_event import recording_emit

pytestmark = pytest.mark.asyncio


class TestGenerationProgressImpl:
    async def test_non_tool_result_skipped(self):
        emit, events = recording_emit()
        await generation_progress_impl(
            {"event_type": "other"},
            emit=emit,
            redis=object(),
        )
        assert events == []

    async def test_no_sid_skipped(self):
        emit, events = recording_emit()
        await generation_progress_impl(
            {"event_type": "tool_result", "sid": "", "run_id": "r1"},
            emit=emit,
            redis=object(),
        )
        assert events == []

    async def test_no_run_id_skipped(self):
        emit, events = recording_emit()
        await generation_progress_impl(
            {"event_type": "tool_result", "sid": "s1"},
            emit=emit,
            redis=object(),
        )
        assert events == []

    async def test_no_resource_or_entry_id_skipped(self):
        emit, events = recording_emit()
        await generation_progress_impl(
            {"event_type": "tool_result", "sid": "s1", "run_id": "r1", "result": {}},
            emit=emit,
            redis=object(),
        )
        assert events == []

    async def test_resource_progress_emitted(self, redis_client):
        emit, events = recording_emit()
        previous = globals_mod.redis_client
        globals_mod.redis_client = redis_client
        try:
            await init_run_trackers(
                redis_client,
                run_id="r1",
                num_agents=1,
                num_resources=5,
                units=[
                    WorkUnit(
                        agent_id="a1", target_type="resource", target_name="prompts"
                    ),
                    WorkUnit(
                        agent_id="a1", target_type="resource", target_name="names"
                    ),
                    WorkUnit(
                        agent_id="a1", target_type="resource", target_name="images"
                    ),
                    WorkUnit(
                        agent_id="a1", target_type="resource", target_name="videos"
                    ),
                    WorkUnit(
                        agent_id="a1", target_type="resource", target_name="documents"
                    ),
                ],
            )
            await generation_progress_impl(
                {
                    "event_type": "tool_result",
                    "sid": "s1",
                    "run_id": "r1",
                    "artifact_type": "agent",
                    "group_id": "g1",
                    "agent_id": "a1",
                    "result": {
                        "resource_id": "res-1",
                        "resource_type": "prompts",
                    },
                },
                emit=emit,
                redis=redis_client,
            )
            legacy_completed = await redis_client.hget(
                "resource_progress:r1", "completed"
            )
        finally:
            globals_mod.redis_client = previous

        assert len(events) == 1
        assert events[0].event == "generation_channel"
        assert events[0].data["type"] == "progress"
        assert events[0].data["completed_resources"] == 1
        assert events[0].data["total_resources"] == 5
        assert events[0].data["percentage"] == 20
        assert events[0].data["last_completed_resource"] == "prompts"
        assert legacy_completed == b"1"

    async def test_entry_progress_emitted_without_legacy_increment(self, redis_client):
        emit, events = recording_emit()
        previous = globals_mod.redis_client
        globals_mod.redis_client = redis_client
        try:
            await init_run_trackers(
                redis_client,
                run_id="r1",
                num_agents=1,
                num_resources=3,
                units=[
                    WorkUnit(
                        agent_id="a1", target_type="entry", target_name="contents"
                    ),
                    WorkUnit(
                        agent_id="a1", target_type="entry", target_name="messages"
                    ),
                    WorkUnit(
                        agent_id="a1", target_type="entry", target_name="problems"
                    ),
                ],
            )
            await generation_progress_impl(
                {
                    "event_type": "tool_result",
                    "sid": "s1",
                    "run_id": "r1",
                    "artifact_type": "agent",
                    "group_id": "g1",
                    "agent_id": "a1",
                    "result": {
                        "entry_id": "ent-1",
                        "entry_type": "contents",
                    },
                },
                emit=emit,
                redis=redis_client,
            )
            legacy_completed = await redis_client.hget(
                "resource_progress:r1", "completed"
            )
        finally:
            globals_mod.redis_client = previous

        assert len(events) == 1
        assert events[0].data["percentage"] == 33
        assert events[0].data["last_completed_resource"] == "contents"
        assert legacy_completed == b"0"

    async def test_agent_id_defaults_to_unknown(self, redis_client):
        emit, events = recording_emit()
        previous = globals_mod.redis_client
        globals_mod.redis_client = redis_client
        try:
            await init_run_trackers(
                redis_client,
                run_id="r1",
                num_agents=1,
                num_resources=1,
                units=[
                    WorkUnit(
                        agent_id="unknown",
                        target_type="resource",
                        target_name="names",
                    )
                ],
            )
            await generation_progress_impl(
                {
                    "event_type": "tool_result",
                    "sid": "s1",
                    "run_id": "r1",
                    "result": {"resource_id": "res-1", "resource_type": "names"},
                },
                emit=emit,
                redis=redis_client,
            )
            units = await redis_client.hgetall("run:r1:units")
        finally:
            globals_mod.redis_client = previous

        assert len(events) == 1
        assert any(key.decode().startswith("unknown:resource:names") for key in units)

    async def test_tracker_error_falls_back_to_1_1(self):
        emit, events = recording_emit()
        previous = globals_mod.redis_client
        globals_mod.redis_client = None
        try:
            await generation_progress_impl(
                {
                    "event_type": "tool_result",
                    "sid": "s1",
                    "run_id": "missing-run",
                    "result": {"resource_id": "res-1", "resource_type": "names"},
                },
                emit=emit,
                redis=object(),
            )
        finally:
            globals_mod.redis_client = previous

        assert len(events) == 1
        assert events[0].data["completed_resources"] == 1
        assert events[0].data["total_resources"] == 1
        assert events[0].data["percentage"] == 100

    async def test_percentage_capped_at_100(self, redis_client):
        emit, events = recording_emit()
        previous = globals_mod.redis_client
        globals_mod.redis_client = redis_client
        try:
            await init_run_trackers(
                redis_client,
                run_id="r1",
                num_agents=1,
                num_resources=5,
                units=[
                    WorkUnit(agent_id="a1", target_type="resource", target_name=f"r{i}")
                    for i in range(5)
                ],
            )
            for index in range(6):
                await generation_progress_impl(
                    {
                        "event_type": "tool_result",
                        "sid": "s1",
                        "run_id": "r1",
                        "agent_id": "a1",
                        "result": {
                            "resource_id": f"res-{index}",
                            "resource_type": f"r{min(index, 4)}",
                        },
                    },
                    emit=emit,
                    redis=redis_client,
                )
        finally:
            globals_mod.redis_client = previous

        assert events[-1].data["percentage"] == 100
