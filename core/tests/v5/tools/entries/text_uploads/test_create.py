"""Tests for create_text_upload."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.text_uploads.get import get_text_upload
from app.tools.entries.texts.create import create_text
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    text = await create_text(conn, session_id=session.id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )
    return session, text, upload


async def test_creates_text_upload_entry(conn, profile_id):
    session, text, upload = await _deps(conn, profile_id)
    result = await create_text_upload(
        conn, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_text_upload_exists_in_table(conn, profile_id):
    session, text, upload = await _deps(conn, profile_id)
    result = await create_text_upload(
        conn, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_text_upload(conn, result.id)

    assert row is not None
    assert row.text_id == text.id
    assert row.upload_id == upload.id
    assert row.session_id == session.id
    assert row.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session, text, upload = await _deps(conn, profile_id)
    result = await create_text_upload(
        conn, text_id=text.id, upload_id=upload.id, session_id=session.id, mcp=True
    )

    row = await get_text_upload(conn, result.id)

    assert row is not None
    assert row.mcp is True
