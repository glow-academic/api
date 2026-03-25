"""Tests for search_images."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.images.create import create_image
from app.tools.entries.images.search import search_images
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.images.create import (
    create_image as create_image_resource,
)

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id, redis_client):
    session = await create_session(conn, profile_id=profile_id)
    resource = await create_image_resource(
        conn, name="test", description="test", redis=redis_client
    )
    image = await create_image(conn, session_id=session.id, images_id=resource.id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="/test/image.png",
        mime_type="image/png",
        size=2048,
    )
    await create_image_upload(
        conn, image_id=image.id, upload_id=upload.id, session_id=session.id
    )
    return image, resource.id


async def test_returns_all_without_filter(conn, profile_id, redis_client):
    await _setup(conn, profile_id, redis_client)

    items = await search_images(conn, bypass_mv=True)

    assert len(items) >= 1


async def test_filters_by_images_ids(conn, profile_id, redis_client):
    _, images_id = await _setup(conn, profile_id, redis_client)

    items = await search_images(conn, images_ids=[images_id], bypass_mv=True)

    assert len(items) >= 1
    assert all(item.images_id == images_id for item in items)


async def test_filters_by_nonexistent_images_ids(conn, profile_id, redis_client):
    await _setup(conn, profile_id, redis_client)

    items = await search_images(conn, images_ids=[nonexistent_id()], bypass_mv=True)

    assert items == []


async def test_pagination_limit(conn, profile_id, redis_client):
    await _setup(conn, profile_id, redis_client)

    items = await search_images(conn, limit=1, bypass_mv=True)

    assert len(items) <= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id, redis_client):
    image, images_id = await _setup(conn, profile_id, redis_client)

    items = await search_images(conn, images_ids=[images_id], bypass_mv=True)

    image_ids = [item.image_id for item in items]
    assert image.id in image_ids
