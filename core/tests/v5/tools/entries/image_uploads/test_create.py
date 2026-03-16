"""Tests for create_image_upload."""

import pytest

from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.image_uploads.get import get_image_upload
from app.tools.entries.images.create import create_image
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    image = await create_image(conn, session_id=session.id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/photo.jpg",
        mime_type="image/jpeg",
        size=4096,
    )
    return session, image, upload


async def test_creates_image_upload_entry(conn, profile_id):
    session, image, upload = await _deps(conn, profile_id)
    result = await create_image_upload(
        conn, image_id=image.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_image_upload_exists_in_table(conn, profile_id):
    session, image, upload = await _deps(conn, profile_id)
    result = await create_image_upload(
        conn, image_id=image.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_image_upload(conn, result.id)

    assert row is not None
    assert row.image_id == image.id
    assert row.upload_id == upload.id
    assert row.session_id == session.id
    assert row.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session, image, upload = await _deps(conn, profile_id)
    result = await create_image_upload(
        conn, image_id=image.id, upload_id=upload.id, session_id=session.id, mcp=True
    )

    row = await get_image_upload(conn, result.id)

    assert row is not None
    assert row.mcp is True
