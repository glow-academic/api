"""Tests for create_message_upload."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.message_uploads.get import get_message_upload
from app.tools.entries.messages.create import create_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    message = await create_message(conn, run_id=run.id, role="assistant")
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/attachment.pdf",
        mime_type="application/pdf",
        size=2048,
    )
    return session, message, upload


async def test_creates_message_upload_entry(conn, profile_id):
    session, message, upload = await _deps(conn, profile_id)
    result = await create_message_upload(
        conn, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_message_upload_exists_in_table(conn, profile_id):
    session, message, upload = await _deps(conn, profile_id)
    result = await create_message_upload(
        conn, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_message_upload(conn, result.id)

    assert row is not None
    assert row.message_id == message.id
    assert row.upload_id == upload.id
    assert row.session_id == session.id
    assert row.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session, message, upload = await _deps(conn, profile_id)
    result = await create_message_upload(
        conn,
        message_id=message.id,
        upload_id=upload.id,
        session_id=session.id,
        mcp=True,
    )

    row = await get_message_upload(conn, result.id)

    assert row is not None
    assert row.mcp is True
