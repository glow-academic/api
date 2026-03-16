"""Tests for create_upload."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.uploads.get import get_upload

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_creates_upload_entry(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )

    assert result.id is not None


async def test_upload_exists_in_table(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )

    upload = await get_upload(conn, result.id)

    assert upload is not None
    assert upload.session_id == session.id
    assert upload.file_path == "test/file.txt"
    assert upload.mime_type == "text/plain"
    assert upload.size == 1024
    assert upload.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=512,
        mcp=True,
    )

    upload = await get_upload(conn, result.id)

    assert upload is not None
    assert upload.mcp is True
