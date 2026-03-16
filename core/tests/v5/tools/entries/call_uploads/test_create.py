"""Tests for create_call_upload."""

import pytest

from app.tools.entries.call_uploads.create import create_call_upload
from app.tools.entries.call_uploads.get import get_call_upload
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/response.json",
        mime_type="application/json",
        size=512,
    )
    return session, call, upload


async def test_creates_call_upload_entry(conn, profile_id):
    session, call, upload = await _deps(conn, profile_id)
    result = await create_call_upload(
        conn, call_id=call.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_call_upload_exists_in_table(conn, profile_id):
    session, call, upload = await _deps(conn, profile_id)
    result = await create_call_upload(
        conn, call_id=call.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_call_upload(conn, result.id)

    assert row is not None
    assert row.call_id == call.id
    assert row.upload_id == upload.id
    assert row.session_id == session.id
    assert row.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session, call, upload = await _deps(conn, profile_id)
    result = await create_call_upload(
        conn, call_id=call.id, upload_id=upload.id, session_id=session.id, mcp=True
    )

    row = await get_call_upload(conn, result.id)

    assert row is not None
    assert row.mcp is True
