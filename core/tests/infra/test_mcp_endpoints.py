"""Tests for MCP tool registration + dispatch via execute_infra_operation."""

from __future__ import annotations

from app.infra.mcp.register import (
    _annotations_for,
    _find_tool_def,
    register_tools,
)
from app.infra.mcp.tool_graph import get_mcp_tool_graph


def test_tool_graph_returns_pairs_from_infra_ops():
    graph = get_mcp_tool_graph()

    assert len(graph) > 20
    assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in graph)
    assert ("persona", "get") in graph
    assert ("scenario", "search") in graph


def test_annotations_mark_read_ops_as_read_only():
    ann = _annotations_for("get", "Persona Get")

    assert ann.readOnlyHint is True
    assert ann.destructiveHint is False
    assert ann.idempotentHint is True
    assert ann.title == "Persona Get"


def test_annotations_mark_write_ops_as_not_read_only():
    create_ann = _annotations_for("create", "Persona Create")
    delete_ann = _annotations_for("delete", "Persona Delete")
    update_ann = _annotations_for("update", "Persona Update")

    assert create_ann.readOnlyHint is False
    assert delete_ann.readOnlyHint is False
    assert delete_ann.destructiveHint is True
    assert update_ann.readOnlyHint is False
    assert update_ann.idempotentHint is True


def test_find_tool_def_matches_on_permission_pair():
    tool_defs = [
        {
            "name": "Persona Get",
            "_permissions": [{"artifact": "persona", "operation": "get"}],
        },
        {
            "name": "Activity Search",
            "_permissions": [{"artifact": "activity", "operation": "search"}],
        },
    ]

    assert _find_tool_def(tool_defs, "persona", "get") is tool_defs[0]
    assert _find_tool_def(tool_defs, "activity", "search") is tool_defs[1]
    assert _find_tool_def(tool_defs, "persona", "delete") is None


def test_find_tool_def_handles_multi_permission_tool():
    td = {
        "name": "Cross Artifact Create",
        "_permissions": [
            {"artifact": "persona", "operation": "create"},
            {"artifact": "scenario", "operation": "create"},
        ],
    }

    assert _find_tool_def([td], "persona", "create") is td
    assert _find_tool_def([td], "scenario", "create") is td
    assert _find_tool_def([td], "cohort", "create") is None


def test_register_tools_registers_every_catalog_entry():
    class FakeServer:
        def __init__(self):
            self.registrations: dict[str, dict] = {}

        def tool(self, *, name, title, description, annotations, **_):
            def _decorator(fn):
                self.registrations[name] = {
                    "fn": fn,
                    "title": title,
                    "description": description,
                    "annotations": annotations,
                }
                return fn

            return _decorator

    server = FakeServer()
    graph = get_mcp_tool_graph()

    register_tools(server, graph)

    assert len(server.registrations) == len(graph)
    assert "get_persona" in server.registrations
    assert "search_scenario" in server.registrations

    get_persona = server.registrations["get_persona"]
    assert get_persona["annotations"].readOnlyHint is True
    assert get_persona["title"] == "Persona Get"
