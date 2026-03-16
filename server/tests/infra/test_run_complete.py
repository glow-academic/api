"""Integration tests for run_complete_impl using real tracker state."""

from __future__ import annotations

import uuid

import pytest

from app.infra.websocket.run_complete_impl import run_complete_impl
from app.infra.websocket.run_tracker import (
    WorkUnit,
    cleanup_run,
    init_run,
    record_agent_done,
    record_unit_soft,
)
from app.infra.websocket.socket_event import recording_emit
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.names.create import create_name
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


async def _run_graph(conn, redis_client):
    profile = await create_profile(conn, redis_client)
    session = await create_session(conn, profile_id=profile.id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(
        conn,
        group_id=group.id,
        session_id=session.id,
        profiles_id=profile.id,
    )
    return profile, session, group, run


def _base_data(
    *, profile_id: str, profiles_id: str, session_id: str, run_id: str, **overrides
):
    data = {
        "sid": "sid-1",
        "run_id": run_id,
        "group_id": "g1",
        "artifact_type": "agent",
        "modality": "text",
        "session_id": session_id,
        "profile_id": profile_id,
        "profiles_id": profiles_id,
        "assistant_output": "",
        "input_text_tokens": 0,
        "output_text_tokens": 0,
        "tool_results": [],
        "metadata": {},
    }
    data.update(overrides)
    return data


class TestRunCompleteImpl:
    async def test_no_sid_emits_nothing(self, conn, redis_client):
        emit, events = recording_emit()
        await run_complete_impl({"sid": ""}, emit=emit, conn=conn, redis=redis_client)
        assert events == []

    async def test_audio_modality_emits_generate_and_returns(self, conn, redis_client):
        emit, events = recording_emit()
        data = {
            "sid": "sid-1",
            "group_id": "g1",
            "artifact_type": "agent",
            "modality": "audio",
            "profile_id": str(uuid.uuid4()),
            "profiles_id": str(uuid.uuid4()),
            "session_id": str(uuid.uuid4()),
            "metadata": {},
        }

        await run_complete_impl(data, emit=emit, conn=conn, redis=redis_client)

        assert len(events) == 1
        assert events[0].event == "generate"
        assert events[0].data["group_id"] == "g1"

    async def test_incomplete_run_returns_without_events(self, conn, redis_client):
        profile, session, _group, run = await _run_graph(conn, redis_client)
        run_id = str(run.id)

        await init_run(
            redis_client,
            run_id=run_id,
            units=[
                WorkUnit(
                    agent_id="agent-a", target_type="resource", target_name="names"
                ),
                WorkUnit(
                    agent_id="agent-b", target_type="resource", target_name="names"
                ),
            ],
            num_agents=2,
        )

        emit, events = recording_emit()
        await run_complete_impl(
            _base_data(
                profile_id=str(profile.id),
                profiles_id=str(profile.id),
                session_id=str(session.id),
                run_id=run_id,
            ),
            emit=emit,
            conn=conn,
            redis=redis_client,
        )

        assert events == []
        await cleanup_run(redis_client, run_id=run_id)

    async def test_uncontested_run_promotes_and_persists_outputs(
        self, conn, redis_client, tmp_path
    ):
        profile, session, _group, run = await _run_graph(conn, redis_client)
        soft_name = await create_name(
            conn, "run-complete-name", redis_client, soft=True
        )
        run_id = str(run.id)

        await init_run(
            redis_client,
            run_id=run_id,
            units=[
                WorkUnit(
                    agent_id="agent-a", target_type="resource", target_name="names"
                ),
            ],
            num_agents=1,
        )
        await record_unit_soft(
            redis_client,
            run_id=run_id,
            agent_id="agent-a",
            target_type="resource",
            target_name="names",
            result_id=str(soft_name.id),
        )

        emit, events = recording_emit()
        await run_complete_impl(
            _base_data(
                profile_id=str(profile.id),
                profiles_id=str(profile.id),
                session_id=str(session.id),
                run_id=run_id,
                assistant_output="assistant reply",
                input_text_tokens=10,
                output_text_tokens=25,
            ),
            emit=emit,
            conn=conn,
            redis=redis_client,
            upload_folder=tmp_path,
        )

        message_role = await conn.fetchval(
            "SELECT role FROM messages_entry WHERE run_id = $1 ORDER BY created_at DESC LIMIT 1",
            run.id,
        )
        active = await conn.fetchval(
            "SELECT active FROM names_resource WHERE id = $1",
            soft_name.id,
        )
        token_count = await conn.fetchval(
            "SELECT COUNT(*) FROM tokens_entry WHERE run_id = $1",
            run.id,
        )

        assert len(events) == 1
        assert events[0].event == "generation_channel"
        assert events[0].data["type"] == "complete"
        assert message_role == "assistant"
        assert active is True
        assert token_count == 1
        assert await redis_client.exists(f"run:{run_id}:meta") == 0

    async def test_contested_run_emits_test_proceed_and_stores_resolution_context(
        self, conn, redis_client
    ):
        profile, session, _group, run = await _run_graph(conn, redis_client)
        test_id = str(uuid.uuid4())
        run_id = str(run.id)

        await init_run(
            redis_client,
            run_id=run_id,
            units=[
                WorkUnit(
                    agent_id="agent-a", target_type="resource", target_name="names"
                ),
                WorkUnit(
                    agent_id="agent-b", target_type="resource", target_name="names"
                ),
            ],
            num_agents=2,
        )
        await record_unit_soft(
            redis_client,
            run_id=run_id,
            agent_id="agent-a",
            target_type="resource",
            target_name="names",
            result_id=str(uuid.uuid4()),
        )
        await record_unit_soft(
            redis_client,
            run_id=run_id,
            agent_id="agent-b",
            target_type="resource",
            target_name="names",
            result_id=str(uuid.uuid4()),
        )
        await record_agent_done(redis_client, run_id=run_id, tool_results=[])

        emit, events = recording_emit()
        await run_complete_impl(
            _base_data(
                profile_id=str(profile.id),
                profiles_id=str(profile.id),
                session_id=str(session.id),
                run_id=run_id,
                metadata={"generation_test_id": test_id},
            ),
            emit=emit,
            conn=conn,
            redis=redis_client,
        )

        stored = await redis_client.get(f"generation_resolution:{test_id}")

        assert len(events) == 1
        assert events[0].event == "test_proceed"
        assert events[0].data["test_id"] == test_id
        assert stored is not None
        assert await redis_client.exists(f"run:{run_id}:meta") == 1

        await cleanup_run(redis_client, run_id=run_id)

    async def test_chat_artifact_emits_attempt_chat_started(self, conn, redis_client):
        profile, session, _group, run = await _run_graph(conn, redis_client)
        soft_name = await create_name(
            conn, "chat-complete-name", redis_client, soft=True
        )
        run_id = str(run.id)

        await init_run(
            redis_client,
            run_id=run_id,
            units=[
                WorkUnit(
                    agent_id="agent-a", target_type="resource", target_name="names"
                ),
            ],
            num_agents=1,
        )
        await record_unit_soft(
            redis_client,
            run_id=run_id,
            agent_id="agent-a",
            target_type="resource",
            target_name="names",
            result_id=str(soft_name.id),
        )

        emit, events = recording_emit()
        await run_complete_impl(
            _base_data(
                profile_id=str(profile.id),
                profiles_id=str(profile.id),
                session_id=str(session.id),
                run_id=run_id,
                artifact_type="chat",
                metadata={"attempt_id": "attempt-1", "attempt_chat_id": "chat-1"},
            ),
            emit=emit,
            conn=conn,
            redis=redis_client,
        )

        assert [event.event for event in events] == [
            "generation_channel",
            "attempt_chat_started",
        ]
        assert events[1].data["chat_id"] == "chat-1"

    async def test_attempt_artifact_skips_duplicate_grade_complete_when_already_emitted(
        self, conn, redis_client
    ):
        profile, session, _group, run = await _run_graph(conn, redis_client)
        soft_name = await create_name(
            conn, "attempt-grade-complete-name", redis_client, soft=True
        )
        run_id = str(run.id)

        await init_run(
            redis_client,
            run_id=run_id,
            units=[
                WorkUnit(
                    agent_id="agent-a", target_type="resource", target_name="names"
                ),
            ],
            num_agents=1,
        )
        await record_unit_soft(
            redis_client,
            run_id=run_id,
            agent_id="agent-a",
            target_type="resource",
            target_name="names",
            result_id=str(soft_name.id),
        )

        emit, events = recording_emit()
        await run_complete_impl(
            _base_data(
                profile_id=str(profile.id),
                profiles_id=str(profile.id),
                session_id=str(session.id),
                run_id=run_id,
                artifact_type="attempt",
                metadata={
                    "attempt_id": "attempt-1",
                    "chat_id": "chat-1",
                    "grade_id": "grade-1",
                    "grade_complete_emitted": True,
                },
            ),
            emit=emit,
            conn=conn,
            redis=redis_client,
        )

        assert [event.event for event in events] == ["generation_channel"]
