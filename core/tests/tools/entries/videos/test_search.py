"""Tests for search_videos."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.video_uploads.create import create_video_upload
from app.tools.entries.videos.create import create_video
from app.tools.entries.videos.search import search_videos
from app.tools.resources.videos.create import (
    create_video as create_video_resource,
)

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id, redis_client):
    session = await create_session(conn, profile_id=profile_id)
    resource = await create_video_resource(
        conn, name="test", description="test", redis=redis_client
    )
    video = await create_video(
        conn, session_id=session.id, length_seconds=120, videos_id=resource.id
    )
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/video.mp4",
        mime_type="video/mp4",
        size=2048,
    )
    await create_video_upload(
        conn, video_id=video.id, upload_id=upload.id, session_id=session.id
    )
    return video, resource.id


async def test_finds_created_entry(conn, profile_id, redis_client):
    video, videos_id = await _setup(conn, profile_id, redis_client)
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY videos_mv")

    items = await search_videos(conn, videos_ids=[videos_id])

    ids = [item.video_id for item in items]
    assert video.id in ids


async def test_filters_by_videos_ids(conn, profile_id, redis_client):
    await _setup(conn, profile_id, redis_client)
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY videos_mv")

    items = await search_videos(conn, videos_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, profile_id, redis_client):
    video, videos_id = await _setup(conn, profile_id, redis_client)
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY videos_mv")

    items = await search_videos(conn, videos_ids=[videos_id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id, redis_client):
    await _setup(conn, profile_id, redis_client)
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY videos_mv")

    items = await search_videos(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id, redis_client):
    video, videos_id = await _setup(conn, profile_id, redis_client)

    items = await search_videos(conn, videos_ids=[videos_id], bypass_mv=True)

    ids = [item.video_id for item in items]
    assert video.id in ids
