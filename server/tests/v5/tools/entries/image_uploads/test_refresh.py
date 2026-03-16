"""Tests for refresh_image_uploads."""

import pytest

from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.image_uploads.refresh import refresh_image_uploads
from app.tools.entries.images.create import create_image
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    parent = await create_image(conn, session_id=session.id)
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
    result = await create_image_upload(
        conn, image_id=parent.id, upload_id=upload.id, session_id=session.id
    )

    row = await conn.fetchrow(
        "SELECT id FROM image_uploads_mv WHERE id = $1", result.id
    )
    assert row is None

    await refresh_image_uploads(conn)

    row = await conn.fetchrow(
        "SELECT id FROM image_uploads_mv WHERE id = $1", result.id
    )
    assert row is not None
    assert row["id"] == result.id
