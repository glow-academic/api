"""Tests for MCP tool graph — which endpoints are exposed as MCP tools."""

from __future__ import annotations

import pytest

from app.infra.mcp.tool_graph import get_mcp_tool_graph

pytestmark = pytest.mark.asyncio


async def test_tool_graph_returns_list_of_tuples():
    """get_mcp_tool_graph returns a non-empty list of (artifact, operation) tuples."""
    graph = get_mcp_tool_graph()

    assert isinstance(graph, list)
    assert len(graph) > 0
    for item in graph:
        assert isinstance(item, tuple)
        assert len(item) == 2
        artifact, operation = item
        assert isinstance(artifact, str)
        assert isinstance(operation, str)


async def test_tool_graph_contains_expected_artifacts():
    """The tool graph includes known artifact types."""
    graph = get_mcp_tool_graph()
    artifacts = {artifact for artifact, _ in graph}

    # Verify a sample of expected artifacts
    assert "cohort" in artifacts
    assert "persona" in artifacts
    assert "scenario" in artifacts
    assert "simulation" in artifacts
    assert "dashboard" in artifacts


async def test_tool_graph_contains_expected_operations():
    """The tool graph includes expected CRUD operations for content artifacts."""
    graph = get_mcp_tool_graph()
    graph_set = set(graph)

    # Content artifacts should have full CRUD
    for artifact in ("cohort", "persona", "scenario", "simulation"):
        assert (artifact, "get") in graph_set
        assert (artifact, "search") in graph_set
        assert (artifact, "delete") in graph_set
        assert (artifact, "draft") in graph_set


async def test_tool_graph_has_no_duplicates():
    """No duplicate (artifact, operation) pairs exist."""
    graph = get_mcp_tool_graph()
    assert len(graph) == len(set(graph))


