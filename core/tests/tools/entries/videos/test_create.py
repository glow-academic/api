"""Tests for create_video."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.videos.create import create_video
from app.tools.entries.videos.get import get_video
from app.tools.resources.videos.create import (
    create_video as create_video_resource,
)

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_creates_video_entry(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_video(conn, session_id=session.id)

    assert result.id is not None


async def test_video_exists_in_table(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_video(conn, session_id=session.id)

    video = await get_video(conn, result.id)

    assert video is not None
    assert video.session_id == session.id
    assert video.active is True


async def test_passes_length_seconds(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_video(conn, session_id=session.id, length_seconds=300)

    video = await get_video(conn, result.id)

    assert video is not None
    assert video.length_seconds == 300


async def test_passes_mcp_flag(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_video(conn, session_id=session.id, mcp=True)

    video = await get_video(conn, result.id)

    assert video is not None
    assert video.mcp is True


async def test_links_videos_resource(conn, profile_id, redis_client):
    session = await _session(conn, profile_id)
    resource = await create_video_resource(
        conn, name="test", description="test", redis=redis_client
    )
    result = await create_video(conn, session_id=session.id, videos_id=resource.id)

    assert result.id is not None
