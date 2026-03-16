"""Tests for generate_prepare_impl — EmitFn pattern.

Orchestrates context resolution, run creation, and agent dispatch.
Uses recording_emit() to capture events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from tests.helpers import nonexistent_id

from app.infra.websocket.generate_prepare_impl import generate_prepare_impl
from app.infra.websocket.prepare_types import AgentDispatch, LLMConfig, MessageSpec
from app.infra.websocket.socket_event import recording_emit

_PROFILE_ID = "00000000-0000-0000-0000-000000000001"
_PROFILES_ID = "00000000-0000-0000-0000-000000000002"
_SESSION_ID = "00000000-0000-0000-0000-000000000003"
_GROUP_ID = "00000000-0000-0000-0000-000000000004"


@dataclass(frozen=True)
class FakeArtifactConfig:
    artifact_type: str = "agent"
    valid_resource_types: list[str] = field(
        default_factory=lambda: ["names", "descriptions"]
    )
    entry_types: list[str] = field(default_factory=lambda: ["problems", "messages"])
    requires_draft: bool = False
    has_artifact_id: bool = True
    prepare_sql_path: str = ""
    draft_view_key: str = ""
    fetcher_id_kwarg: str = ""


def _base_data(**overrides: object) -> dict:
    d: dict = {
        "sid": "s1",
        "profile_id": _PROFILE_ID,
        "profiles_id": _PROFILES_ID,
        "session_id": _SESSION_ID,
        "group_id": _GROUP_ID,
        "artifact_types": [{"name": "agent", "operation": "get"}],
        "resource_types": [{"name": "names", "operation": "create"}],
    }
    d.update(overrides)
    return d


@pytest.mark.asyncio
class TestGeneratePrepareImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await generate_prepare_impl(
            {"sid": ""},
            emit=emit,
            pool=object(),
            conn=object(),
            redis=object(),
            artifact_config=FakeArtifactConfig(),
        )
        assert events == []

    async def test_no_profile_emits_error(self):
        emit, events = recording_emit()
        await generate_prepare_impl(
            _base_data(profile_id=None),
            emit=emit,
            pool=object(),
            conn=object(),
            redis=object(),
            artifact_config=FakeArtifactConfig(),
        )
        assert len(events) == 1
        assert events[0].event == "generate_call_error"
        assert "Profile not found" in events[0].data["error_message"]

    async def test_no_profiles_id_emits_error(self):
        emit, events = recording_emit()
        await generate_prepare_impl(
            _base_data(profiles_id=None),
            emit=emit,
            pool=object(),
            conn=object(),
            redis=object(),
            artifact_config=FakeArtifactConfig(),
        )
        assert len(events) == 1
        assert "Profiles resource" in events[0].data["error_message"]

    async def test_no_session_emits_error(self):
        emit, events = recording_emit()
        await generate_prepare_impl(
            _base_data(session_id=None),
            emit=emit,
            pool=object(),
            conn=object(),
            redis=object(),
            artifact_config=FakeArtifactConfig(),
        )
        assert len(events) == 1
        assert "Session not found" in events[0].data["error_message"]

    async def test_no_group_id_emits_error(self):
        emit, events = recording_emit()
        await generate_prepare_impl(
            _base_data(group_id=None),
            emit=emit,
            pool=object(),
            conn=object(),
            redis=object(),
            artifact_config=FakeArtifactConfig(),
        )
        assert len(events) == 1
        assert "group_id is required" in events[0].data["error_message"]

    async def test_no_artifact_config_emits_error(self):
        emit, events = recording_emit()
        await generate_prepare_impl(
            _base_data(),
            emit=emit,
            pool=object(),
            conn=object(),
            redis=object(),
            artifact_config=None,
        )
        assert len(events) == 1
        assert "Unknown artifact_type" in events[0].data["error_message"]

    async def test_invalid_profile_uuid_emits_error(self):
        emit, events = recording_emit()
        await generate_prepare_impl(
            _base_data(profile_id="not-a-uuid"),
            emit=emit,
            pool=object(),
            conn=object(),
            redis=object(),
            artifact_config=FakeArtifactConfig(),
        )
        assert len(events) == 1
        assert "Invalid request" in events[0].data["error_message"]

    async def test_context_resolution_failure_emits_error(self, pool, redis_client):
        emit, events = recording_emit()
        async with pool.acquire() as conn:
            await generate_prepare_impl(
                _base_data(
                    profile_id=str(nonexistent_id()),
                    profiles_id=str(nonexistent_id()),
                    session_id=str(nonexistent_id()),
                    group_id=str(nonexistent_id()),
                    artifact_types=[{"name": "persona", "operation": "get"}],
                ),
                emit=emit,
                pool=pool,
                conn=conn,
                redis=redis_client,
                artifact_config=FakeArtifactConfig(artifact_type="persona"),
            )
        assert len(events) == 1
        assert "Failed to resolve context" in events[0].data["error_message"]

    async def test_no_agents_emits_error(
        self,
        pool,
        redis_client,
        profile_identity_factory,
        persona_context_factory,
    ):
        emit, events = recording_emit()
        profile = await profile_identity_factory(departments=[], emails=[])
        persona = await persona_context_factory()

        async with pool.acquire() as conn:
            await generate_prepare_impl(
                _base_data(
                    profile_id=str(profile.artifact_id),
                    profiles_id=str(profile.profile_resource_id),
                    session_id=str(nonexistent_id()),
                    group_id=str(persona.group_id),
                    artifact_types=[{"name": "persona", "operation": "get"}],
                    artifact_id=str(persona.persona_id),
                ),
                emit=emit,
                pool=pool,
                conn=conn,
                redis=redis_client,
                artifact_config=FakeArtifactConfig(artifact_type="persona"),
            )
        assert len(events) == 1
        assert "No system/agent" in events[0].data["error_message"]

    async def test_happy_path_emits_started_and_artifact(self):
        """Full path: context → run → dispatch → emit started + generate_artifact."""
        emit, events = recording_emit()
        agent_id = uuid4()
        run_id = uuid4()

        agent = SimpleNamespace(
            id=agent_id,
            model_id=uuid4(),
            prompt_id=None,
            instruction_ids=[],
            tool_ids=[],
            rubric_id=None,
            department_ids=None,
        )

        ws_ctx = SimpleNamespace(
            agents=[agent],
            models=[],
            providers=[],
            tools=[],
            prompts=[],
            instructions=[],
            args=[],
            args_outputs=[],
            scores=SimpleNamespace(best={"names": SimpleNamespace(agent_id=agent_id)}),
            artifacts={},
        )

        mock_run = SimpleNamespace(id=run_id)
        llm_config = LLMConfig(
            model="gpt-4o",
            api_key="sk-test",
            base_url="https://api.openai.com",
            temperature=0.7,
            reasoning=None,
            provider="openai",
            voice=None,
            quality=None,
        )

        recorded_runs: list[dict[str, object]] = []
        recorded_trackers: list[dict[str, object]] = []
        recorded_messages: list[dict[str, object]] = []

        async def fake_resolve_context(*args, **kwargs):
            return ws_ctx

        def fake_resolve_agent_config(*args, **kwargs):
            return llm_config

        async def fake_create_run(conn, **kwargs):
            recorded_runs.append(kwargs)
            return mock_run

        async def fake_init_run_trackers(redis, **kwargs):
            recorded_trackers.append(kwargs)

        async def fake_persist_run_message(
            conn, *, run_id, session_id, role, content
        ) -> None:
            recorded_messages.append(
                {
                    "run_id": run_id,
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                }
            )

        def fake_build_agent_dispatch(**kwargs):
            return AgentDispatch(
                agent_id=agent_id,
                resource_types=["names"],
                entry_types=[],
                messages=[
                    MessageSpec(
                        role="developer",
                        content="Do the thing",
                        raw_text="Do the thing",
                        persist=True,
                    )
                ],
                llm_config=llm_config,
                scoped_tools=[],
                metadata=kwargs["payload_metadata"],
                developer_instruction_templates=None,
            )

        await generate_prepare_impl(
            _base_data(user_instructions=["User asks for output"]),
            emit=emit,
            pool=object(),
            conn=object(),
            redis=object(),
            artifact_config=FakeArtifactConfig(),
            resolve_websocket_context_fn=fake_resolve_context,
            build_agent_groups_from_scores_fn=lambda **kwargs: {agent_id: ["names"]},
            build_jinja_from_ws_ctx_fn=lambda *args, **kwargs: {},
            resolve_agent_config_fn=fake_resolve_agent_config,
            create_run_fn=fake_create_run,
            init_run_trackers_fn=fake_init_run_trackers,
            persist_run_message_fn=fake_persist_run_message,
            build_agent_dispatch_fn=fake_build_agent_dispatch,
        )

        # Should emit generation_started + generate_artifact
        assert len(events) >= 2
        event_names = [e.event for e in events]
        assert "generation_started" in event_names
        assert "generate_artifact" in event_names

        started = next(e for e in events if e.event == "generation_started")
        assert started.data["artifact_type"] == "agent"
        assert started.data["run_id"] == str(run_id)

        artifact = next(e for e in events if e.event == "generate_artifact")
        assert artifact.data["artifact_type"] == "agent"
        assert artifact.data["run_id"] == str(run_id)
        assert artifact.data["llm_config"]["model"] == "gpt-4o"
        assert artifact.data["messages"][-1] == {
            "role": "user",
            "content": "User asks for output",
        }
        assert recorded_runs == [
            {
                "group_id": UUID(_GROUP_ID),
                "session_id": UUID(_SESSION_ID),
                "profiles_id": UUID(_PROFILES_ID),
                "agent_ids": [agent_id],
            }
        ]
        assert len(recorded_trackers) == 1
        assert recorded_trackers[0]["run_id"] == str(run_id)
        assert [(m["role"], m["content"]) for m in recorded_messages] == [
            ("developer", "Do the thing"),
            ("user", "User asks for output"),
        ]
