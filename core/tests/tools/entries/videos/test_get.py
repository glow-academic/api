"""Tests for get_video."""

import pytest
from app.tools.entries.sessions.create import create_session
from app.tools.entries.videos.create import create_video
from app.tools.entries.videos.get import get_video
from app.tools.resources.videos.create import (
    create_video as create_video_resource,
)
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_videos(conn, redis_client, session_id):
    created = _created(await create_video(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'video_id', None) or getattr(created, 'id', None) or getattr(created, 'video', None)
    item = await get_video(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    item = await get_video(conn, nonexistent_id(), redis_client)

    assert item is None
