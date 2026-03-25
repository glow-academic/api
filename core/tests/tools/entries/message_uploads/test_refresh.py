"""Tests for refresh_message_uploads."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.message_uploads.refresh import refresh_message_uploads
from app.tools.entries.messages.create import create_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    parent = await create_message(conn, run_id=run.id, role="user")
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/file.bin",
        mime_type="application/octet-stream",
        size=1024,
    )
    return session, parent, upload


async def test_new_upload_appears_in_mv_after_refresh(conn, profile_id):
    session, parent, upload = await _setup(conn, profile_id)
    result = await create_message_upload(
        conn, message_id=parent.id, upload_id=upload.id, session_id=session.id
    )

    row = await conn.fetchrow(
        "SELECT id FROM message_uploads_mv WHERE id = $1", result.id
    )
    assert row is None

    await refresh_message_uploads(conn)

    row = await conn.fetchrow(
        "SELECT id FROM message_uploads_mv WHERE id = $1", result.id
    )
    assert row is not None
    assert row["id"] == result.id
