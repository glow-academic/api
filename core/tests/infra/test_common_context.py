"""Integration tests for infra.common_context — real DB, no mocks."""

import pytest
from tests.helpers import nonexistent_id

from app.infra.common_context import CommonContext, resolve_common_context
from app.infra.profile_identity_context import resolve_profile_identity_context

pytestmark = pytest.mark.asyncio


class TestResolveCommonContext:
    async def test_profile_not_found_returns_none(self, pool, redis_client):
        result = await resolve_common_context(
            pool,
            redis_client,
            profile_id=nonexistent_id(),
        )

        assert result is None

    async def test_profile_without_settings_returns_empty_tool_graph(
        self, pool, redis_client, profile_identity_factory
    ):
        profile_fixture = await profile_identity_factory(
            departments=[],
            emails=[],
        )

        result = await resolve_common_context(
            pool,
            redis_client,
            profile_id=profile_fixture.artifact_id,
        )

        assert result is not None
        assert isinstance(result, CommonContext)
        assert result.profile.settings_id is None
        assert result.tool_graph.tools == []
        assert result.runs.total_count == 0
        assert result.runs.items == []

    async def test_resolves_context_for_ground_up_profile(
        self, pool, redis_client, profile_identity_factory
    ):
        profile_fixture = await profile_identity_factory(
            departments=[],
            emails=[],
        )

        expected_profile = await resolve_profile_identity_context(
            pool,
            profile_fixture.artifact_id,
            redis_client,
        )

        result = await resolve_common_context(
            pool,
            redis_client,
            profile_id=profile_fixture.artifact_id,
        )

        assert expected_profile is not None
        assert result is not None
        assert isinstance(result, CommonContext)
        assert result.profile == expected_profile
        assert result.tool_graph.tools == []
        assert result.runs.total_count >= 0

    async def test_uses_pre_resolved_profile_when_provided(
        self, pool, redis_client, profile_identity_factory
    ):
        profile_fixture = await profile_identity_factory(
            departments=[],
            emails=[],
        )
        profile = await resolve_profile_identity_context(
            pool,
            profile_fixture.artifact_id,
            redis_client,
        )

        result = await resolve_common_context(
            pool,
            redis_client,
            profile_id=profile_fixture.artifact_id,
            profile=profile,
        )

        assert profile is not None
        assert result is not None
        assert result.profile is profile
        assert isinstance(result.tool_graph.tools, list)
        assert result.runs.total_count >= 0

    async def test_profile_with_setting_graph_resolves_real_tool_graph(
        self, pool, redis_client, setting_graph_factory
    ):
        fixture = await setting_graph_factory()

        result = await resolve_common_context(
            pool,
            redis_client,
            profile_id=fixture.profile_artifact_id,
        )

        assert result is not None
        assert result.profile.profiles_id == fixture.profile_resource_id
        assert result.profile.primary_department_id == fixture.department_id
        assert result.profile.settings_id == fixture.setting_id
        assert {tool.system_id for tool in result.tool_graph.tools} == {
            fixture.system_id
        }
        assert {tool.agent_id for tool in result.tool_graph.tools} == {fixture.agent_id}
        assert {tool.tool_id for tool in result.tool_graph.tools} == {fixture.tool_id}
        assert {
            (tool.target_type, tool.target, tool.operation)
            for tool in result.tool_graph.tools
        } == {("artifact", target, fixture.operation) for target in fixture.artifacts}
