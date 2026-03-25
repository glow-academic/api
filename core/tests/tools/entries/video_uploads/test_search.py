"""Tests for video_uploads search."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.video_uploads.create import create_video_upload
from app.tools.entries.video_uploads.search import search_video_uploads
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


async def test_search_finds_created(conn, profile_id):
    session, video, upload = await _deps(conn, profile_id)
    await create_video_upload(
        conn, video_id=video.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_video_uploads(conn, video_ids=[video.id])

    assert len(results) == 1
    assert results[0].video_id == video.id
    assert results[0].upload_id == upload.id


async def test_search_filters_by_video_id(conn, profile_id):
    session, video, upload = await _deps(conn, profile_id)
    await create_video_upload(
        conn, video_id=video.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_video_uploads(conn, video_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_filters_by_upload_id(conn, profile_id):
    session, video, upload = await _deps(conn, profile_id)
    await create_video_upload(
        conn, video_id=video.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_video_uploads(conn, upload_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_pagination(conn, profile_id):
    session, video, upload1 = await _deps(conn, profile_id)
    upload2 = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/clip2.mp4",
        mime_type="video/mp4",
        size=8192,
    )
    await create_video_upload(
        conn, video_id=video.id, upload_id=upload1.id, session_id=session.id
    )
    await create_video_upload(
        conn, video_id=video.id, upload_id=upload2.id, session_id=session.id
    )

    results = await search_video_uploads(conn, video_ids=[video.id], limit=1)

    assert len(results) == 1
