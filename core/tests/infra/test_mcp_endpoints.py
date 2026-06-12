"""Tests for MCP tool registration + dispatch via execute_infra_operation."""

from __future__ import annotations

from app.infra.mcp.register import (
    _annotations_for,
    _clamp_page_size_inputs,
    register_tools,
)
from app.infra.mcp.resolve import McpContext, allowed_tool_names
from app.infra.mcp.tool_catalog import slugify_tool_name
from app.infra.shared_types import MAX_PAGE_SIZE


def test_slugify_tool_name_handles_common_shapes():
    assert slugify_tool_name("Activity Export") == "activity_export"
    assert slugify_tool_name("Create Content") == "create_content"
    assert slugify_tool_name("Test Grade - A") == "test_grade_a"
    assert slugify_tool_name("") == ""


def test_annotations_mark_write_tool_as_not_read_only():
    td = {
        "name": "Create Content",
        "_permissions": [
            {"artifact": "persona", "operation": "create"},
            {"artifact": "scenario", "operation": "create"},
        ],
    }
    ann = _annotations_for(td, "Create Content")

    assert ann.readOnlyHint is False
    assert ann.destructiveHint is False
    assert ann.title == "Create Content"


def test_annotations_mark_delete_tool_as_destructive():
    td = {
        "name": "Delete Content",
        "_permissions": [
            {"artifact": "persona", "operation": "delete"},
        ],
    }
    ann = _annotations_for(td, "Delete Content")

    assert ann.readOnlyHint is False
    assert ann.destructiveHint is True


def test_annotations_mark_read_only_tool_correctly():
    td = {
        "name": "Search Content",
        "_permissions": [
            {"artifact": "persona", "operation": "search"},
            {"artifact": "scenario", "operation": "search"},
        ],
    }
    ann = _annotations_for(td, "Search Content")

    assert ann.readOnlyHint is True
    assert ann.destructiveHint is False


def test_allowed_tool_names_emits_one_slug_per_tool_def():
    ctx = McpContext(
        profile_id=None,  # type: ignore[arg-type]
        agent_id=None,
        tool_defs=[
            {
                "name": "Create Content",
                "_permissions": [
                    {"artifact": "persona", "operation": "create"},
                    {"artifact": "scenario", "operation": "create"},
                    {"artifact": "cohort", "operation": "create"},
                ],
            },
            {
                "name": "Search Content",
                "_permissions": [
                    {"artifact": "persona", "operation": "search"},
                ],
            },
            {
                "name": "Delete Infrastructure",
                "_permissions": [
                    {"artifact": "agent", "operation": "delete"},
                ],
            },
        ],
        role_permissions=[
            ("persona", "create"),
            ("persona", "search"),
            ("scenario", "create"),
            # ("agent", "delete") deliberately omitted → Delete Infrastructure filtered out
        ],
    )

    names = allowed_tool_names(ctx)

    # Three tools on agent but one is filtered because profile lacks agent/delete.
    assert names == {"create_content", "search_content"}


def test_allowed_tool_names_requires_at_least_one_overlap():
    """A single permission overlap is enough to expose a multi-target tool."""
    ctx = McpContext(
        profile_id=None,  # type: ignore[arg-type]
        agent_id=None,
        tool_defs=[
            {
                "name": "Create Content",
                "_permissions": [
                    {"artifact": "persona", "operation": "create"},
                    {"artifact": "scenario", "operation": "create"},
                ],
            }
        ],
        role_permissions=[("persona", "create")],  # only one overlap
    )

    assert allowed_tool_names(ctx) == {"create_content"}


# ─────────────────────────────────────────────────────────────────────────────
# R4: the MCP dispatch builds its own tool signature with no le bound, so a
# page-size arg flows unbounded into the SQL LIMIT. The REST request models cap
# it at le=200 (MAX_PAGE_SIZE); _clamp_page_size_inputs mirrors that shared cap
# onto the MCP read/search path before resolve_tool_spec.
# ─────────────────────────────────────────────────────────────────────────────


def test_clamp_page_size_clamps_oversized_to_max():
    """An oversized MCP page_size is clamped to MAX_PAGE_SIZE (no unbounded LIMIT)."""
    out = _clamp_page_size_inputs({"page_size": 1_000_000, "search": "x"})
    assert out["page_size"] == MAX_PAGE_SIZE
    assert out["search"] == "x"  # other inputs untouched


def test_clamp_page_size_clamps_page_limit_too():
    """page_limit (the activity/list size arg) is also capped."""
    assert _clamp_page_size_inputs({"page_limit": 9999})["page_limit"] == MAX_PAGE_SIZE


def test_clamp_page_size_string_input_is_clamped():
    """FastMCP may pass a stringified int — it's coerced then clamped."""
    assert _clamp_page_size_inputs({"page_size": "5000"})["page_size"] == MAX_PAGE_SIZE


def test_clamp_page_size_below_one_floored():
    """A zero/negative page_size floors to 1 (matches REST ge=1)."""
    assert _clamp_page_size_inputs({"page_size": 0})["page_size"] == 1
    assert _clamp_page_size_inputs({"page_size": -10})["page_size"] == 1


def test_clamp_page_size_in_range_unchanged():
    """A legitimate page_size within bounds passes through untouched."""
    assert _clamp_page_size_inputs({"page_size": 12})["page_size"] == 12
    assert _clamp_page_size_inputs({"page_size": MAX_PAGE_SIZE})["page_size"] == MAX_PAGE_SIZE


def test_clamp_page_size_no_page_arg_is_noop():
    """Tools with no page-size arg are unaffected (e.g. offset-only)."""
    assert _clamp_page_size_inputs({"page_offset": 99999, "search": "x"}) == {
        "page_offset": 99999,
        "search": "x",
    }


def test_clamp_page_size_non_numeric_left_for_downstream():
    """A non-numeric value is left untouched so resolve_tool_spec/Pydantic reports it."""
    assert _clamp_page_size_inputs({"page_size": "abc"})["page_size"] == "abc"


def test_register_tools_registers_each_tool_def_once():
    class FakeServer:
        def __init__(self):
            self.registrations: dict[str, dict] = {}

        def tool(self, *, name, title, description, annotations, **_):
            def _decorator(fn):
                self.registrations[name] = {
                    "title": title,
                    "description": description,
                    "annotations": annotations,
                }
                return fn

            return _decorator

    server = FakeServer()
    tool_defs = [
        {
            "name": "Create Content",
            "description": "create content resources",
            "_permissions": [{"artifact": "persona", "operation": "create"}],
        },
        {
            "name": "Search Content",
            "description": "search content resources",
            "_permissions": [{"artifact": "persona", "operation": "search"}],
        },
    ]

    register_tools(server, tool_defs)

    assert set(server.registrations.keys()) == {"create_content", "search_content"}
    assert server.registrations["create_content"]["annotations"].readOnlyHint is False
    assert server.registrations["search_content"]["annotations"].readOnlyHint is True
