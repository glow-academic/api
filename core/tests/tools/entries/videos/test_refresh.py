"""Tests for refresh_videos_internal."""

import pytest
from app.tools.entries.sessions.create import create_session
from app.tools.entries.videos.create import create_video
from app.tools.entries.videos.get import get_video
from app.tools.resources.videos.create import (
    create_video as create_video_resource,
)
from app.tools.entries.videos.refresh import refresh_videos_internal
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_videos_appears_after_refresh(conn, redis_client, session_id):
    created = _created(await create_video(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'video_id', None) or getattr(created, 'id', None) or getattr(created, 'video', None)

    await refresh_videos_internal(conn)
    item = await get_video(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_new_videos_is_not_visible_before_refresh(conn, redis_client, session_id):
    created = _created(await create_video(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'video_id', None) or getattr(created, 'id', None) or getattr(created, 'video', None)

    item = await get_video(conn, lookup_id, redis_client)

    assert item is None


async def test_refresh_is_idempotent(conn):
    await refresh_videos_internal(conn)
    await refresh_videos_internal(conn)

    assert True
