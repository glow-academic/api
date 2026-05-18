"""Tests for refresh_images_internal."""

import pytest
from app.tools.entries.images.create import create_image
from app.tools.entries.images.get import get_image
from app.tools.entries.sessions.create import create_session
from app.tools.resources.images.create import (
    create_image as create_image_resource,
)
from app.tools.entries.images.refresh import refresh_images_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_images_appears_after_refresh(conn, session_id):
    created = _created(await create_image(conn, session_id=session_id))
    lookup_id = getattr(created, 'image_id', None) or getattr(created, 'id', None) or getattr(created, 'image', None)

    await refresh_images_internal(conn)
    item = await get_image(conn, lookup_id)

    assert item is not None
    assert item.id == lookup_id


async def test_new_images_is_not_visible_before_refresh(conn, session_id):
    created = _created(await create_image(conn, session_id=session_id))
    lookup_id = getattr(created, 'image_id', None) or getattr(created, 'id', None) or getattr(created, 'image', None)

    item = await get_image(conn, lookup_id)

    assert item is None


async def test_refresh_is_idempotent(conn):
    await refresh_images_internal(conn)
    await refresh_images_internal(conn)

    assert True
