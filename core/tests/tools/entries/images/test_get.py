"""Tests for get_image."""

import pytest
from app.tools.entries.images.create import create_image
from app.tools.entries.images.get import get_image
from app.tools.entries.sessions.create import create_session
from app.tools.resources.images.create import (
    create_image as create_image_resource,
)
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_images(conn, redis_client, session_id):
    created = _created(await create_image(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'image_id', None) or getattr(created, 'id', None) or getattr(created, 'image', None)
    item = await get_image(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    item = await get_image(conn, nonexistent_id(), redis_client)

    assert item is None


async def test_returns_created_item_after_second_lookup(conn, redis_client, session_id):
    created = _created(await create_image(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'image_id', None) or getattr(created, 'id', None) or getattr(created, 'image', None)
    first = await get_image(conn, lookup_id, redis_client)
    second = await get_image(conn, lookup_id, redis_client)

    assert first is not None
    assert second is not None
    assert second.id == lookup_id
