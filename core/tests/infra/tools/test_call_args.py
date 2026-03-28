"""Tests for call_args — resolve_tool, resolve_tool_for_entry, record_call_args."""

import uuid

import pytest

from app.infra.tools.call_args import (
    ToolArgInfo,
    ToolInfo,
    record_call_args,
    resolve_tool,
    resolve_tool_for_entry,
)
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


# -- ToolArgInfo / ToolInfo dataclasses ----------------------------------------


async def test_tool_arg_info_stores_fields():
    arg_id = uuid.uuid4()
    info = ToolArgInfo(args_id=arg_id, name="title", field_type="string")

    assert info.args_id == arg_id
    assert info.name == "title"
    assert info.field_type == "string"


async def test_tool_info_stores_tool_id_and_args():
    tool_id = uuid.uuid4()
    arg = ToolArgInfo(args_id=uuid.uuid4(), name="body", field_type="text")
    info = ToolInfo(tool_id=tool_id, args=[arg])

    assert info.tool_id == tool_id
    assert len(info.args) == 1
    assert info.args[0].name == "body"


# -- resolve_tool --------------------------------------------------------------


async def test_resolve_tool_returns_none_for_missing_tool(conn, redis_client, monkeypatch):
    """resolve_tool returns None when no matching tool exists in tools_resource."""
    monkeypatch.setattr(
        "app.infra.tools.call_args.get_redis_client", lambda: redis_client
    )

    result = await resolve_tool(conn, "create", "nonexistent_target_" + unique_tag())
    assert result is None


async def test_resolve_tool_returns_none_for_invalid_scope(conn, redis_client, monkeypatch):
    """resolve_tool returns None when scope is not entries/resources/artifacts."""
    monkeypatch.setattr(
        "app.infra.tools.call_args.get_redis_client", lambda: redis_client
    )

    result = await resolve_tool(conn, "create", "attempts", scope="invalid_scope")
    assert result is None


async def test_resolve_tool_for_entry_delegates_to_resolve_tool(conn, redis_client, monkeypatch):
    """resolve_tool_for_entry delegates to resolve_tool with scope='entries'."""
    captured = {}

    async def _fake_resolve(conn, operation, target, *, scope="entries"):
        captured["scope"] = scope
        captured["operation"] = operation
        captured["target"] = target
        return None

    monkeypatch.setattr("app.infra.tools.call_args.resolve_tool", _fake_resolve)

    await resolve_tool_for_entry(conn, "create", "attempts")

    assert captured["scope"] == "entries"
    assert captured["operation"] == "create"
    assert captured["target"] == "attempts"


# -- record_call_args (no-op) --------------------------------------------------


async def test_record_call_args_is_noop(conn):
    """record_call_args is a no-op after migration 29 — should complete without error."""
    tool_info = ToolInfo(tool_id=uuid.uuid4(), args=[])
    call_id = uuid.uuid4()

    # Should not raise
    await record_call_args(conn, call_id, tool_info, {"key": "value"})


async def test_record_call_args_with_mcp_flag(conn):
    """record_call_args accepts mcp flag without error."""
    tool_info = ToolInfo(tool_id=uuid.uuid4(), args=[
        ToolArgInfo(args_id=uuid.uuid4(), name="content", field_type="string"),
    ])

    await record_call_args(conn, uuid.uuid4(), tool_info, {"content": "hi"}, mcp=True)
