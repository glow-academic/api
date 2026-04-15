"""Integration tests for infra.websocket_context — real DB, no mocks."""

import pytest
from tests.helpers import nonexistent_id

from app.infra.types import ArtifactRequest
from app.infra.websocket_context import resolve_websocket_context

pytestmark = pytest.mark.asyncio


class TestResolveWebsocketContext:
    async def test_profile_not_found_returns_none(self, pool, redis_client):
        result = await resolve_websocket_context(
            pool,
            redis_client,
            profile_id=nonexistent_id(),
            requests=[],
        )

        assert result is None

    async def test_empty_requests_returns_empty_context(
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

    async def test_single_persona_request_returns_context(
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
        assert result.scores is not None
        assert result.profile is not None
