"""Tests for tool_executor — execute_tool_call routing and error handling."""

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.infra.tools.tool_executor import execute_tool_call
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


# -- missing layer returns error -----------------------------------------------


async def test_returns_error_when_no_layer_specified(conn, monkeypatch):
    """When neither entry_type nor resource_type is given, returns error JSON."""
    result = await execute_tool_call(
        conn,
        tool_name="test_tool",
        arguments={"name": "foo"},
        tool_id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        upload_folder=Path("/tmp"),
    )

    data = json.loads(result)
    assert data["success"] is False
    assert "No resource_type or entry_type" in data["message"]
    assert data["error_stage"] == "tool_resolve"


# -- unregistered tool fn returns error ----------------------------------------


async def test_returns_error_when_tool_fn_not_registered(conn, monkeypatch, tmp_path):
    """When resolve_tool_fn returns None, returns a tool_resolve error."""
    tag = unique_tag()

    # Stub template rendering to return some values
    async def _fake_render(conn, tool_id, arguments):
        return {"col": "val"}

    async def _fake_map(conn, name, values, tool_id=None, is_entry=False):
        return {"col": "val"}

    monkeypatch.setattr(
        "app.infra.tools.tool_executor.render_tool_template", _fake_render
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.map_template_values_to_table_columns",
        _fake_map,
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.resolve_tool_fn",
        lambda layer, name, operation: None,
    )

    result = await execute_tool_call(
        conn,
        tool_name="test_tool_" + tag,
        arguments={"name": "foo"},
        tool_id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        upload_folder=tmp_path,
        entry_type="nonexistent_type_" + tag,
    )

    data = json.loads(result)
    assert data["success"] is False
    assert "No registered tool function" in data["message"]
    assert data["error_stage"] == "tool_resolve"


# -- empty mapped values for create returns error -----------------------------


async def test_returns_error_when_no_values_to_insert(conn, monkeypatch, tmp_path):
    """When template rendering returns empty values for create, returns error."""
    async def _fake_render(conn, tool_id, arguments):
        return {}

    async def _fake_map(conn, name, values, tool_id=None, is_entry=False):
        return {}

    monkeypatch.setattr(
        "app.infra.tools.tool_executor.render_tool_template", _fake_render
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.map_template_values_to_table_columns",
        _fake_map,
    )

    result = await execute_tool_call(
        conn,
        tool_name="test_tool",
        arguments={},
        tool_id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        upload_folder=tmp_path,
        entry_type="attempts",
    )

    data = json.loads(result)
    assert data["success"] is False
    assert "No values to insert" in data["message"]
    assert data["error_stage"] == "tool_execute"


# -- successful execution via entry layer --------------------------------------


async def test_successful_entry_tool_returns_success_json(
    conn, profile_id, session_id, group_id, monkeypatch, tmp_path, redis_client
):
    """Full happy path: render -> resolve -> create_tool_call -> success JSON."""
    from app.infra.tools.entries.types import CreateToolSetupResponse

    fake_run_id = uuid.uuid4()
    fake_call_id = uuid.uuid4()
    fake_msg_id = uuid.uuid4()
    fake_result_id = uuid.uuid4()

    async def _fake_render(conn, tool_id, arguments):
        return {"content": arguments.get("content", "")}

    async def _fake_map(conn, name, values, tool_id=None, is_entry=False):
        return values

    def _fake_resolve(layer, name, operation):
        async def _tool_fn(conn, **kwargs):
            return json.dumps({"ok": True})
        return _tool_fn

    async def _fake_create_tool_call(conn, **kwargs):
        return CreateToolSetupResponse(
            run_id=fake_run_id,
            call_id=fake_call_id,
            message_id=fake_msg_id,
            result_id=fake_result_id,
            result=json.dumps({"ok": True}),
            text_id=uuid.uuid4(),
            call_upload_junction_id=None,
        )

    monkeypatch.setattr(
        "app.infra.tools.tool_executor.render_tool_template", _fake_render
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.map_template_values_to_table_columns",
        _fake_map,
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.resolve_tool_fn", _fake_resolve
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.create_tool_call", _fake_create_tool_call
    )

    result = await execute_tool_call(
        conn,
        tool_name="create_note",
        arguments={"content": "hello"},
        tool_id=uuid.uuid4(),
        group_id=group_id,
        session_id=session_id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        entry_type="notes",
    )

    data = json.loads(result)
    assert data["success"] is True
    assert data["entry_type"] == "notes"
    assert data["run_id"] == str(fake_run_id)
    assert data["entry_id"] == str(fake_result_id)


# -- resource layer injects redis ----------------------------------------------


async def test_resource_layer_injects_redis(
    conn, profile_id, session_id, group_id, monkeypatch, tmp_path, redis_client
):
    """When resource_type is provided, redis is injected into fn_arguments."""
    from app.infra.tools.entries.types import CreateToolSetupResponse

    captured_args = {}

    async def _fake_render(conn, tool_id, arguments):
        return {"name": "test"}

    async def _fake_map(conn, name, values, tool_id=None, is_entry=False):
        return values

    def _fake_resolve(layer, name, operation):
        async def _tool_fn(conn, **kwargs):
            return json.dumps({"ok": True})
        return _tool_fn

    async def _fake_create_tool_call(conn, **kwargs):
        captured_args.update(kwargs)
        return CreateToolSetupResponse(
            run_id=uuid.uuid4(),
            call_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
            result_id=uuid.uuid4(),
            result=json.dumps({"ok": True}),
            text_id=uuid.uuid4(),
            call_upload_junction_id=None,
        )

    monkeypatch.setattr(
        "app.infra.tools.tool_executor.render_tool_template", _fake_render
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.map_template_values_to_table_columns",
        _fake_map,
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.resolve_tool_fn", _fake_resolve
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.create_tool_call", _fake_create_tool_call
    )
    monkeypatch.setattr(
        "app.infra.tools.tool_executor.get_redis_client", lambda: redis_client
    )

    result = await execute_tool_call(
        conn,
        tool_name="create_cohort",
        arguments={"name": "test"},
        tool_id=uuid.uuid4(),
        group_id=group_id,
        session_id=session_id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        resource_type="cohorts",
    )

    data = json.loads(result)
    assert data["success"] is True
    assert data["resource_type"] == "cohorts"
    # The arguments passed to create_tool_call should include redis
    assert "arguments" in captured_args
    assert "redis" in captured_args["arguments"]


# -- exception during execution returns error JSON -----------------------------


async def test_exception_during_execution_returns_error(conn, monkeypatch, tmp_path):
    """Exceptions during execution are caught and returned as error JSON."""
    async def _exploding_render(conn, tool_id, arguments):
        raise RuntimeError("template engine exploded")

    monkeypatch.setattr(
        "app.infra.tools.tool_executor.render_tool_template", _exploding_render
    )

    result = await execute_tool_call(
        conn,
        tool_name="create_note",
        arguments={"content": "hello"},
        tool_id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        upload_folder=tmp_path,
        entry_type="notes",
    )

    data = json.loads(result)
    assert data["success"] is False
    assert "template engine exploded" in data["message"]
    assert data["error_stage"] == "tool_execute"
