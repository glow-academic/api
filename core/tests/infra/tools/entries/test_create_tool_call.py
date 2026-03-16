"""Tests for create_tool_call."""

import json

import pytest

from app.infra.tools.entries.create_tool_call import create_tool_call
from app.tools.entries.calls.get import get_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.get import get_message
from app.tools.entries.runs.get import get_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.texts.get import get_text
from app.tools.resources.tools.create import (
    create_tool as create_tool_resource,
)

pytestmark = pytest.mark.asyncio


# -- helpers -------------------------------------------------------------------


async def _success_tool(conn, **kwargs):
    return json.dumps({"success": True, "message": "Created"})


async def _failing_tool(conn, **kwargs):
    raise ValueError("something broke")


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    return session, group


# -- with tool_id --------------------------------------------------------------


async def test_with_tool_returns_all_ids(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)
    tool = await create_tool_resource(conn)

    result = await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"},
        tool_id=tool.id,
    )

    assert result.run_id is not None
    assert result.call_id is not None
    assert result.message_id is not None
    assert result.text_id is not None
    assert result.call_upload_junction_id is not None
    assert json.loads(result.result)["success"] is True


async def test_with_tool_writes_both_files(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)
    tool = await create_tool_resource(conn)

    await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"},
        tool_id=tool.id,
    )

    assert (tmp_path / "text").is_dir()
    assert (tmp_path / "call").is_dir()

    txt_files = list((tmp_path / "text").glob("*.txt"))
    json_files = list((tmp_path / "call").glob("*.json"))
    assert len(txt_files) == 1
    assert len(json_files) == 1


async def test_with_tool_json_has_correct_shape(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)
    tool = await create_tool_resource(conn)

    await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"},
        tool_id=tool.id,
    )

    json_file = list((tmp_path / "call").glob("*.json"))[0]
    data = json.loads(json_file.read_text())
    assert set(data.keys()) == {"call_id", "tool_id", "arguments", "output"}
    assert data["arguments"] == {"name": "Dr. Smith"}
    assert data["tool_id"] == str(tool.id)


async def test_with_tool_txt_has_output(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)
    tool = await create_tool_resource(conn)

    await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"},
        tool_id=tool.id,
    )

    txt_file = list((tmp_path / "text").glob("*.txt"))[0]
    data = json.loads(txt_file.read_text())
    assert data["success"] is True


async def test_with_tool_creates_db_entries(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)
    tool = await create_tool_resource(conn)

    result = await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"},
        tool_id=tool.id,
    )

    run = await get_run(conn, result.run_id)
    assert run is not None

    call = await get_call(conn, result.call_id)
    assert call is not None

    message = await get_message(conn, result.message_id)
    assert message is not None

    text = await get_text(conn, result.text_id)
    assert text is not None


# -- without tool_id -----------------------------------------------------------


async def test_without_tool_returns_ids(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)

    result = await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_success_tool,
        arguments={"prompt": "Summarize"},
    )

    assert result.run_id is not None
    assert result.call_id is None
    assert result.message_id is not None
    assert result.text_id is not None
    assert result.call_upload_junction_id is None


async def test_without_tool_writes_txt_only(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)

    await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_success_tool,
        arguments={"prompt": "Summarize"},
    )

    assert (tmp_path / "text").is_dir()
    assert not (tmp_path / "call").exists()


async def test_without_tool_creates_db_entries(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)

    result = await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_success_tool,
        arguments={"prompt": "Summarize"},
    )

    run = await get_run(conn, result.run_id)
    assert run is not None

    message = await get_message(conn, result.message_id)
    assert message is not None

    text = await get_text(conn, result.text_id)
    assert text is not None


# -- error handling ------------------------------------------------------------


async def test_failing_tool_still_persists(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)
    tool = await create_tool_resource(conn)

    result = await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_failing_tool,
        arguments={"name": "Dr. Smith"},
        tool_id=tool.id,
    )

    assert result.run_id is not None

    txt_file = list((tmp_path / "text").glob("*.txt"))[0]
    data = json.loads(txt_file.read_text())
    assert data["success"] is False
    assert "something broke" in data["message"]


async def test_returns_raw_result_payload(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)
    tool = await create_tool_resource(conn)

    result = await create_tool_call(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        upload_folder=tmp_path,
        tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"},
        tool_id=tool.id,
    )

    assert result.result is not None
    assert json.loads(result.result)["message"] == "Created"


async def test_raise_on_error_persists_then_reraises(conn, profile_id, tmp_path):
    session, group = await _deps(conn, profile_id)
    tool = await create_tool_resource(conn)

    with pytest.raises(ValueError, match="something broke"):
        await create_tool_call(
            conn,
            group_id=group.id,
            session_id=session.id,
            profile_id=profile_id,
            upload_folder=tmp_path,
            tool_fn=_failing_tool,
            arguments={"name": "Dr. Smith"},
            tool_id=tool.id,
            raise_on_error=True,
        )

    txt_file = list((tmp_path / "text").glob("*.txt"))[0]
    data = json.loads(txt_file.read_text())
    assert data["success"] is False
