"""Integration tests for infra.websocket_context — real DB, no mocks."""

import pytest
from tests.helpers import nonexistent_id

from app.infra.types import ArtifactRequest, ArtifactWebsocketContext
from app.infra.websocket_context import resolve_websocket_context

pytestmark = pytest.mark.asyncio


async def _create_attempt_context_graph(pool, actor):
    from app.tools.entries.attempt.create import create_attempt
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.persona.create import create_persona
    from app.tools.entries.runs.create import create_run

    async with pool.acquire() as conn:
        group = await create_group(conn, session_id=actor.session_id, name="ws-attempt")
        run = await create_run(
            conn,
            group_id=group.id,
            session_id=actor.session_id,
            profiles_id=actor.profiles_id,
        )
        call = await create_call(conn, run_id=run.id, session_id=actor.session_id)
        persona = await create_persona(conn)
        attempt = await create_attempt(
            conn,
            call_id=call.id,
            user_persona_id=persona.id,
            profiles_id=actor.profiles_id,
            name="Websocket Attempt",
            description="Attempt context graph",
        )
        await refresh_attempt(conn)

    return {
        "attempt_id": attempt.id,
        "group_id": group.id,
    }


class TestResolveWebsocketContext:
    async def test_profile_not_found_returns_none(self, pool, redis_client):
        result = await resolve_websocket_context(
            pool,
            redis_client,
            profile_id=nonexistent_id(),
            requests=[],
        )

        assert result is None

    async def test_empty_requests_returns_empty_artifacts(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory(departments=[], emails=[])

        result = await resolve_websocket_context(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            requests=[],
        )

        assert result is not None
        assert result.artifacts == {}
        assert result.systems == []
        assert result.agents == []
        assert result.tools == []

    async def test_unknown_artifact_type_raises(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory(departments=[], emails=[])

        with pytest.raises(ValueError, match="Unknown artifact type: nonexistent"):
            await resolve_websocket_context(
                pool,
                redis_client,
                profile_id=profile.artifact_id,
                requests=[
                    ArtifactRequest(
                        artifact_type="nonexistent",
                        artifact_id=nonexistent_id(),
                        group_id=nonexistent_id(),
                    )
                ],
            )

    async def test_single_persona_request_returns_namespaced_artifact_context(
        self, pool, redis_client, profile_identity_factory, persona_context_factory
    ):
        profile = await profile_identity_factory(departments=[], emails=[])
        persona = await persona_context_factory()

        result = await resolve_websocket_context(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            requests=[
                ArtifactRequest(
                    artifact_type="persona",
                    artifact_id=persona.persona_id,
                    group_id=persona.group_id,
                    draft_id=persona.draft_id,
                    params={"descriptions_search": persona.suggestion_description},
                )
            ],
        )

        assert result is not None
        assert "get.persona" in result.artifacts

        artifact = result.artifacts["get.persona"]
        assert isinstance(artifact, ArtifactWebsocketContext)
        assert artifact.params == {
            "descriptions_search": persona.suggestion_description
        }
        assert "get.names" in artifact.resources
        assert "search.names" in artifact.resources
        assert "get.descriptions" in artifact.resources
        assert "search.descriptions" in artifact.resources
        assert "get.fields" in artifact.resources
        assert "search.fields" in artifact.resources
        assert artifact.entries == {}
        assert [item.id for item in artifact.resources["get.names"]] == [
            persona.draft_name_id
        ]
        suggestion_ids = [item.id for item in artifact.resources["search.descriptions"]]
        assert persona.suggestion_description_id in suggestion_ids

    async def test_resolves_real_systems_from_profile_tool_graph(
        self, pool, redis_client, setting_graph_factory, persona_context_factory
    ):
        profile = await setting_graph_factory()
        persona = await persona_context_factory()

        result = await resolve_websocket_context(
            pool,
            redis_client,
            profile_id=profile.profile_artifact_id,
            requests=[
                ArtifactRequest(
                    artifact_type="persona",
                    artifact_id=persona.persona_id,
                    group_id=persona.group_id,
                )
            ],
        )

        assert result is not None
        assert "get.persona" in result.artifacts
        assert [system.system_id for system in result.systems] == [profile.system_id]
        assert [agent.id for agent in result.agents] == [profile.agent_id]
        assert [tool.id for tool in result.tools] == [profile.tool_id]

    async def test_single_attempt_request_returns_namespaced_artifact_context(
        self, pool, redis_client, setting_graph_factory
    ):
        from tests.infra.route_helpers import create_admin_route_actor

        attempt_resources = [
            "attempt",
            "personas",
            "scenarios",
            "parameters",
            "fields",
            "feedbacks",
            "strengths",
            "improvements",
            "analyses",
            "highlights",
            "replacements",
        ]
        actor = await create_admin_route_actor(
            pool,
            redis_client,
            setting_graph_factory,
            tool_artifacts=attempt_resources,
            group_name="ws-context-attempt",
            role_name_prefix="WS Context Attempt",
        )
        graph = await _create_attempt_context_graph(pool, actor)

        result = await resolve_websocket_context(
            pool,
            redis_client,
            profile_id=actor.profile_id,
            requests=[
                ArtifactRequest(
                    artifact_type="attempt",
                    artifact_id=graph["attempt_id"],
                    group_id=graph["group_id"],
                )
            ],
        )

        assert result is not None
        assert "get.attempt" in result.artifacts

        artifact = result.artifacts["get.attempt"]
        assert isinstance(artifact, ArtifactWebsocketContext)
        assert artifact.params == {}
        assert "get.scenarios" in artifact.resources
        assert "get.personas" in artifact.resources
        assert "get.questions" in artifact.resources
        assert "get.attempts" in artifact.entries
        assert "get.chats" in artifact.entries
        assert "get.messages" in artifact.entries
        assert [attempt.attempt_id for attempt in artifact.entries["get.attempts"]] == [
            graph["attempt_id"]
        ]
        assert len(result.systems) == 1
