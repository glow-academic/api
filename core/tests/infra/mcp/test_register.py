"""Tests for MCP tool registration — introspects route handlers."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from app.infra.mcp.register import (
    _build_tool_args,
    _get_request_model,
    _import_handler,
)

pytestmark = pytest.mark.asyncio


class _SampleRequest(BaseModel):
    name: str
    count: int = 10
    mcp: bool = False


async def _sample_handler(request: _SampleRequest) -> dict:
    return {"ok": True}


async def test_get_request_model_extracts_pydantic_model():
    """_get_request_model finds the first Pydantic model parameter."""
    model = _get_request_model(_sample_handler)

    assert model is _SampleRequest


async def test_get_request_model_returns_none_for_no_model():
    """Returns None when handler has no Pydantic parameter."""

    async def plain_handler(x: int) -> dict:
        return {}

    model = _get_request_model(plain_handler)
    assert model is None


async def test_build_tool_args_extracts_fields():
    """_build_tool_args returns field definitions from a Pydantic model."""
    args = _build_tool_args(_SampleRequest)

    arg_names = {a["name"] for a in args}
    # mcp field should be filtered out
    assert "mcp" not in arg_names
    assert "name" in arg_names
    assert "count" in arg_names


async def test_build_tool_args_marks_required_fields():
    """Required fields (no default) are marked as required."""
    args = _build_tool_args(_SampleRequest)

    by_name = {a["name"]: a for a in args}
    assert by_name["name"]["required"] is True
    assert by_name["count"]["required"] is False


async def test_import_handler_raises_for_nonexistent_module():
    """_import_handler raises when module does not exist."""
    # Clear the cache first to avoid stale entries
    from app.infra.mcp.register import _handler_cache
    _handler_cache.pop("app.routes.nonexistent.missing", None)

    with pytest.raises((ModuleNotFoundError, ValueError)):
        _import_handler("app.routes.nonexistent.missing")


async def test_register_tools_registers_with_fastmcp():
    """register_tools registers tools on a FastMCP server."""
    from app.infra.mcp.register import register_tools

    server = MagicMock()
    registered_tools = []

    def fake_tool():
        def decorator(fn):
            registered_tools.append(fn.__name__)
            return fn
        return decorator

    server.tool = fake_tool

    tool_graph = [("cohort", "get"), ("persona", "search")]

    with patch(
        "app.infra.mcp.register._import_handler",
        side_effect=ValueError("skip"),
    ):
        # register_tools should not fail even if handler import is deferred
        register_tools(server, tool_graph)

    # Tools should be registered with correct naming
    assert "get_cohort" in registered_tools
    assert "search_persona" in registered_tools
