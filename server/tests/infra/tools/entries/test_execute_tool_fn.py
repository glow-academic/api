"""Tests for execute_tool_fn."""

import json

import pytest

from app.infra.tools.entries.execute_tool_fn import execute_tool_fn

pytestmark = pytest.mark.asyncio


async def test_returns_string_output():
    async def tool(conn, **kw):
        return '{"success": true}'

    result = await execute_tool_fn(tool, None, {})
    assert json.loads(result) == {"success": True}


async def test_passes_arguments():
    received = {}

    async def tool(conn, **kw):
        received.update(kw)
        return '{"success": true}'

    await execute_tool_fn(tool, None, {"name": "Dr. Smith", "count": 3})
    assert received == {"name": "Dr. Smith", "count": 3}


async def test_passes_conn():
    received_conn = None

    async def tool(conn, **kw):
        nonlocal received_conn
        received_conn = conn
        return '{"success": true}'

    sentinel = object()
    await execute_tool_fn(tool, sentinel, {})
    assert received_conn is sentinel


async def test_serializes_dict_output():
    async def tool(conn, **kw):
        return {"success": True, "entry_id": "abc"}

    result = await execute_tool_fn(tool, None, {})
    data = json.loads(result)
    assert data == {"success": True, "entry_id": "abc"}


async def test_catches_exception():
    async def tool(conn, **kw):
        raise ValueError("something broke")

    result = await execute_tool_fn(tool, None, {})
    data = json.loads(result)
    assert data["success"] is False
    assert "something broke" in data["message"]


async def test_always_returns_valid_json():
    async def tool(conn, **kw):
        raise RuntimeError("boom")

    result = await execute_tool_fn(tool, None, {})
    json.loads(result)  # should not raise
