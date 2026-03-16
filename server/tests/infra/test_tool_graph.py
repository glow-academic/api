"""Tests for infra.tool_graph — real graph resolution + pure scoring."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from tests.helpers import nonexistent_id

from app.infra.tool_graph import (
    ResolvedTool,
    SettingsToolGraph,
    resolve_tool_graph,
    score_tools,
)
from app.tools.resources.agents.types import GetAgentResponse
from app.tools.resources.settings.create import create_setting
from app.tools.resources.settings.types import GetSettingResponse
from app.tools.resources.systems.types import GetSystemResponse
from app.tools.resources.tools.types import GetToolResponse

NOW = datetime.now(UTC)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _tool(
    *,
    artifacts: list[str] | None = None,
    operation: str = "create",
) -> GetToolResponse:
    return GetToolResponse(
        id=uuid4(),
        name="test-tool",
        description=None,
        operation=operation,
        department_ids=[],
        args_ids=[],
        args_output_ids=[],
        artifacts=artifacts or [],
        created_at=NOW,
        active=True,
        mcp=False,
        generated=False,
    )


def _agent(*, tool_ids: list | None = None) -> GetAgentResponse:
    return GetAgentResponse(
        id=uuid4(),
        name="test-agent",
        description=None,
        department_ids=[],
        temperature=None,
        reasoning=None,
        quality=None,
        model_id=None,
        prompt_id=None,
        rubric_id=None,
        tool_ids=tool_ids or [],
        instruction_ids=[],
        voices=[],
        created_at=NOW,
        active=True,
        mcp=False,
        generated=False,
    )


def _system(*, agent_ids: list | None = None) -> GetSystemResponse:
    return GetSystemResponse(
        id=uuid4(),
        name="test-system",
        description=None,
        agent_ids=agent_ids or [],
        created_at=NOW,
        active=True,
        mcp=False,
        generated=False,
    )


def _setting(*, system_ids: list | None = None) -> GetSettingResponse:
    return GetSettingResponse(
        id=uuid4(),
        name="test-setting",
        description=None,
        department_ids=[],
        provider_key_ids=[],
        auth_ids=[],
        system_ids=system_ids or [],
        created_at=NOW,
        active=True,
        mcp=False,
        generated=False,
    )


def _resolved(
    *,
    system_id=None,
    agent_id=None,
    tool_id=None,
    operation="create",
    target_type="resource",
    target="names",
) -> ResolvedTool:
    return ResolvedTool(
        system_id=system_id or uuid4(),
        agent_id=agent_id or uuid4(),
        tool_id=tool_id or uuid4(),
        operation=operation,
        target_type=target_type,
        target=target,
    )


# ═══════════════════════════════════════════════════════════════════════════
# score_tools — pure unit tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreToolsEmpty:
    def test_empty_graph_returns_none_for_all(self):
        result = score_tools(SettingsToolGraph(), {"names", "colors"})
        assert result.best["names"] is None
        assert result.best["colors"] is None
        assert result.has_any == {"names": False, "colors": False}

    def test_no_matching_targets(self):
        graph = SettingsToolGraph(tools=[_resolved(target="descriptions")])
        result = score_tools(graph, {"names", "colors"})
        assert result.best["names"] is None
        assert result.has_any["names"] is False


class TestScoreToolsSingleAgent:
    def test_single_tool_single_resource(self):
        agent_id = uuid4()
        tool = _resolved(agent_id=agent_id, target="names")
        graph = SettingsToolGraph(tools=[tool])

        result = score_tools(graph, {"names"})
        assert result.best["names"] is tool
        assert result.has_any["names"] is True

    def test_agent_covers_multiple_resources(self):
        agent_id = uuid4()
        t1 = _resolved(agent_id=agent_id, target="names")
        t2 = _resolved(agent_id=agent_id, target="colors")
        graph = SettingsToolGraph(tools=[t1, t2])

        result = score_tools(graph, {"names", "colors"})
        assert result.best["names"] is t1
        assert result.best["colors"] is t2


class TestScoreToolsMultiAgent:
    def test_specialist_wins_over_generalist(self):
        """Agent covering more artifact resources should win."""
        specialist_id = uuid4()
        generalist_id = uuid4()

        # Specialist covers names + colors (2 artifact resources)
        t_spec_names = _resolved(agent_id=specialist_id, target="names")
        t_spec_colors = _resolved(agent_id=specialist_id, target="colors")

        # Generalist covers only names (1 artifact resource)
        t_gen_names = _resolved(agent_id=generalist_id, target="names")

        graph = SettingsToolGraph(tools=[t_spec_names, t_spec_colors, t_gen_names])
        result = score_tools(graph, {"names", "colors"})

        assert result.best["names"] is t_spec_names
        assert result.best["colors"] is t_spec_colors

    def test_tiebreak_by_agent_id(self):
        """Equal coverage — deterministic pick by agent_id."""
        id_a = uuid4()
        id_b = uuid4()

        t_a = _resolved(agent_id=id_a, target="names")
        t_b = _resolved(agent_id=id_b, target="names")

        graph = SettingsToolGraph(tools=[t_a, t_b])
        result = score_tools(graph, {"names"})

        expected = t_a if id_a > id_b else t_b
        assert result.best["names"] is expected


class TestScoreToolsModality:
    def test_available_modalities_computed_from_tools(self):
        """available_modalities is the union of all agent modalities."""
        agent_id = uuid4()
        tool_id = uuid4()
        # Agent has a tool that creates images (entry)
        t1 = _resolved(
            agent_id=agent_id,
            tool_id=tool_id,
            target="images",
            target_type="entry",
            operation="create",
        )
        t2 = _resolved(
            agent_id=agent_id,
            tool_id=tool_id,
            target="names",
            target_type="resource",
            operation="create",
        )
        graph = SettingsToolGraph(tools=[t1, t2])

        result = score_tools(graph, {"images", "names"})
        # get_tool_output_modalities for (create, ["names"], ["images"], []) → {"image", "call"}
        assert "image" in result.available_modalities
        assert "call" in result.available_modalities

    def test_modality_filter_excludes_non_matching_agents(self):
        """modality='image' filters out agents that can't produce images."""
        # Agent A: only creates resources (call modality)
        agent_a = uuid4()
        tool_a = uuid4()
        t_a = _resolved(
            agent_id=agent_a,
            tool_id=tool_a,
            target="names",
            target_type="resource",
            operation="create",
        )

        # Agent B: creates images (image modality)
        agent_b = uuid4()
        tool_b = uuid4()
        t_b_names = _resolved(
            agent_id=agent_b,
            tool_id=tool_b,
            target="names",
            target_type="resource",
            operation="create",
        )
        t_b_images = _resolved(
            agent_id=agent_b,
            tool_id=tool_b,
            target="images",
            target_type="entry",
            operation="create",
        )

        graph = SettingsToolGraph(tools=[t_a, t_b_names, t_b_images])
        result = score_tools(graph, {"names", "images"}, modality="image")

        # Agent A filtered out — only agent B can produce images
        assert result.best["names"] is t_b_names
        assert result.best["images"] is t_b_images

    def test_modality_filter_no_matching_agents_returns_none(self):
        """modality='image' with no image-capable agents → all best = None."""
        agent_id = uuid4()
        tool_id = uuid4()
        t = _resolved(
            agent_id=agent_id,
            tool_id=tool_id,
            target="names",
            target_type="resource",
            operation="create",
        )
        graph = SettingsToolGraph(tools=[t])

        result = score_tools(graph, {"names"}, modality="image")
        assert result.best["names"] is None
        assert result.has_any["names"] is True  # tool exists, just filtered out

    def test_modality_none_behaves_as_before(self):
        """modality=None → no filtering, same behavior as before."""
        agent_id = uuid4()
        tool_id = uuid4()
        t = _resolved(
            agent_id=agent_id,
            tool_id=tool_id,
            target="names",
            target_type="resource",
            operation="create",
        )
        graph = SettingsToolGraph(tools=[t])

        result = score_tools(graph, {"names"}, modality=None)
        assert result.best["names"] is t

    def test_empty_graph_has_empty_modalities(self):
        result = score_tools(SettingsToolGraph(), {"names"})
        assert result.available_modalities == set()


class TestScoreToolsTargetTypes:
    def test_entry_tools(self):
        agent_id = uuid4()
        t = _resolved(agent_id=agent_id, target="contents", target_type="entry")
        graph = SettingsToolGraph(tools=[t])

        result = score_tools(graph, {"contents"})
        assert result.best["contents"] is t
        assert result.best["contents"].target_type == "entry"

    def test_mixed_target_types(self):
        agent_id = uuid4()
        t_res = _resolved(agent_id=agent_id, target="names", target_type="resource")
        t_entry = _resolved(agent_id=agent_id, target="contents", target_type="entry")
        t_art = _resolved(agent_id=agent_id, target="persona", target_type="artifact")

        graph = SettingsToolGraph(tools=[t_res, t_entry, t_art])
        result = score_tools(graph, {"names", "contents", "persona"})

        assert result.best["names"] is t_res
        assert result.best["contents"] is t_entry
        assert result.best["persona"] is t_art


@pytest.mark.asyncio
class TestResolveToolGraph:
    async def test_missing_settings_returns_empty(self, pool, redis_client):
        result = await resolve_tool_graph(pool, nonexistent_id(), redis_client)
        assert result.tools == []

    async def test_setting_with_no_systems_returns_empty(self, pool, redis_client):
        async with pool.acquire() as conn:
            setting = await create_setting(
                conn,
                name=f"empty-setting-{uuid4()}",
                description="No systems",
                system_ids=[],
                redis=redis_client,
            )

        result = await resolve_tool_graph(pool, setting.id, redis_client)
        assert result.tools == []

    async def test_full_chain_produces_real_resolved_tools(
        self, pool, redis_client, setting_graph_factory
    ):
        fixture = await setting_graph_factory(tool_artifacts=["profile", "persona"])

        result = await resolve_tool_graph(pool, fixture.setting_id, redis_client)

        assert len(result.tools) == 2
        assert {tool.target for tool in result.tools} == {"profile", "persona"}
        assert {tool.tool_id for tool in result.tools} == {fixture.tool_id}
        assert {tool.agent_id for tool in result.tools} == {fixture.agent_id}
        assert {tool.system_id for tool in result.tools} == {fixture.system_id}
        assert {tool.operation for tool in result.tools} == {fixture.operation}
        assert {tool.target_type for tool in result.tools} == {"artifact"}
