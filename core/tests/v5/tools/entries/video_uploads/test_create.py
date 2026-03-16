"""Tests for create_video_upload."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.video_uploads.create import create_video_upload
from app.tools.entries.video_uploads.get import get_video_upload
from app.tools.entries.videos.create import create_video

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    video = await create_video(conn, session_id=session.id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/clip.mp4",
        mime_type="video/mp4",
        size=8192,
    )
    return session, video, upload


async def test_creates_video_upload_entry(conn, profile_id):
    session, video, upload = await _deps(conn, profile_id)
    result = await create_video_upload(
        conn, video_id=video.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_video_upload_exists_in_table(conn, profile_id):
    session, video, upload = await _deps(conn, profile_id)
    result = await create_video_upload(
        conn, video_id=video.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_video_upload(conn, result.id)

    assert row is not None
    assert row.video_id == video.id
    assert row.upload_id == upload.id
    assert row.session_id == session.id
    assert row.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session, video, upload = await _deps(conn, profile_id)
    result = await create_video_upload(
        conn, video_id=video.id, upload_id=upload.id, session_id=session.id, mcp=True
    )

    row = await get_video_upload(conn, result.id)

    assert row is not None
    assert row.mcp is True
