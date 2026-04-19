"""Tests for events audit — resolve_artifact_operation_tool."""
import pytest
from uuid import uuid4
from app.infra.events.audit import resolve_artifact_operation_tool
from app.infra.tool_graph import SettingsToolGraph, ResolvedTool
pytestmark = pytest.mark.asyncio

async def test_resolve_returns_none_for_empty_graph():
    graph = SettingsToolGraph(tools=[])
    result = resolve_artifact_operation_tool(graph, artifact="persona", operation="create")
    assert result is None

async def test_resolve_finds_matching_tool():
    tool = ResolvedTool(
        agent_id=uuid4(), tool_id=uuid4(),
        operation="create", target_type="artifact", target="persona",
    )
    graph = SettingsToolGraph(tools=[tool])
    result = resolve_artifact_operation_tool(graph, artifact="persona", operation="create")
    assert result == tool.tool_id

async def test_resolve_ignores_wrong_operation():
    tool = ResolvedTool(
        agent_id=uuid4(), tool_id=uuid4(),
        operation="delete", target_type="artifact", target="persona",
    )
    graph = SettingsToolGraph(tools=[tool])
    result = resolve_artifact_operation_tool(graph, artifact="persona", operation="create")
    assert result is None
