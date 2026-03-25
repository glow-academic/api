"""Tests for create_upload_completion."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.upload_completion.create import (
    create_upload_completion,
)
from app.tools.entries.upload_completion.get import get_upload_completion
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _upload(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )
    return session, upload


async def test_creates_upload_completion_entry(conn, profile_id):
    session, upload = await _upload(conn, profile_id)
    result = await create_upload_completion(
        conn,
        upload_id=upload.id,
        session_id=session.id,
    )

    assert result.id is not None


async def test_upload_completion_exists_in_table(conn, profile_id):
    session, upload = await _upload(conn, profile_id)
    result = await create_upload_completion(
        conn,
        upload_id=upload.id,
        session_id=session.id,
    )

    completion = await get_upload_completion(conn, result.id)

    assert completion is not None
    assert completion.upload_id == upload.id
    assert completion.session_id == session.id
    assert completion.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session, upload = await _upload(conn, profile_id)
    result = await create_upload_completion(
        conn,
        upload_id=upload.id,
        session_id=session.id,
        mcp=True,
    )

    completion = await get_upload_completion(conn, result.id)

    assert completion is not None
    assert completion.mcp is True
