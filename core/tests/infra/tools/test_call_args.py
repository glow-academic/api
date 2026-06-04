"""Tests for call_args — ToolArgInfo, ToolInfo, record_call_args."""

import uuid

import pytest

from app.infra.tools.call_args import (
    ToolArgInfo,
    ToolInfo,
    record_call_args,
)

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
