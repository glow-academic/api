"""Tests for persona audit helpers."""

from uuid import uuid4

from app.infra.persona.audit import resolve_persona_operation_tool
from app.infra.tool_graph import ResolvedTool, SettingsToolGraph


def test_resolve_persona_operation_tool_matches_artifact_and_operation() -> None:
    expected_tool_id = uuid4()
    graph = SettingsToolGraph(
        tools=[
            ResolvedTool(
                system_id=uuid4(),
                agent_id=uuid4(),
                tool_id=uuid4(),
                operation="get",
                target_type="artifact",
                target="scenario",
            ),
            ResolvedTool(
                system_id=uuid4(),
                agent_id=uuid4(),
                tool_id=expected_tool_id,
                operation="get",
                target_type="artifact",
                target="persona",
            ),
        ]
    )

    assert resolve_persona_operation_tool(graph, operation="get") == expected_tool_id


def test_resolve_persona_operation_tool_returns_none_without_match() -> None:
    graph = SettingsToolGraph(
        tools=[
            ResolvedTool(
                system_id=uuid4(),
                agent_id=uuid4(),
                tool_id=uuid4(),
                operation="update",
                target_type="artifact",
                target="persona",
            )
        ]
    )

    assert resolve_persona_operation_tool(graph, operation="get") is None
