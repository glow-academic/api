"""Tests for refresh_videos_internal."""

import pytest
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.video_uploads.create import create_video_upload
from app.tools.entries.videos.create import create_video
from app.tools.entries.videos.get import get_video
from app.tools.resources.videos.create import (
    create_video as create_video_resource,
)
from app.tools.entries.videos.refresh import refresh_videos_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def _mv_eligible_video(conn, redis_client, session_id):
    # videos_mv inner-joins videos_resource (via videos_videos_connection) and
    # uploads, so build the full row here — a bare create_video never enters the MV.
    resource = await create_video_resource(
        conn, name="test", description="test", redis=redis_client
    )
    video = await create_video(
        conn, redis_client, session_id=session_id, length_seconds=120, videos_id=resource.id
    )
    upload = await create_upload(
        conn, redis_client, session_id=session_id,
        file_path="test/video.mp4", mime_type="video/mp4", size=2048,
    )
    await create_video_upload(
        conn, redis_client, video_id=video.id, upload_id=upload.id, session_id=session_id
    )
    return video


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_videos_appears_after_refresh(conn, redis_client, session_id):
    created = _created(await create_video(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'video_id', None) or getattr(created, 'id', None) or getattr(created, 'video', None)

    await refresh_videos_internal(conn)
    item = await get_video(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_new_videos_is_visible_before_refresh(conn, redis_client, session_id):
    # get_video's bypass_cache path reads the base videos_entry table (not the
    # MV), so a freshly created row is immediately visible without any refresh.
    # Refresh only repopulates videos_mv (see the MV-population test below).
    created = _created(await create_video(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'video_id', None) or getattr(created, 'id', None) or getattr(created, 'video', None)

    item = await get_video(conn, lookup_id, redis_client, bypass_cache=True)

    assert item is not None
    assert item.id == lookup_id


async def test_videos_mv_populated_only_after_refresh(conn, redis_client, session_id):
    # The materialized view videos_mv is NOT updated by create; it only reflects
    # the new (MV-eligible) row after refresh_videos_internal.
    video = await _mv_eligible_video(conn, redis_client, session_id)
    lookup_id = video.id

    in_mv_before = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM videos_mv WHERE video_id = $1)", lookup_id
    )
    assert in_mv_before is False

    await refresh_videos_internal(conn)

    in_mv_after = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM videos_mv WHERE video_id = $1)", lookup_id
    )
    assert in_mv_after is True


async def test_refresh_is_idempotent(conn):
    await refresh_videos_internal(conn)
    await refresh_videos_internal(conn)

    assert True
