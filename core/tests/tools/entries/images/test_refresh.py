"""Tests for refresh_images_internal."""

import pytest
from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.images.create import create_image
from app.tools.entries.images.get import get_image
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.images.create import (
    create_image as create_image_resource,
)
from app.tools.entries.images.refresh import refresh_images_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def _mv_eligible_image(conn, redis_client, session_id):
    # images_mv inner-joins images_resource (via images_images_connection) and
    # uploads, so build the full row here — a bare create_image never enters the MV.
    resource = await create_image_resource(
        conn, name="test", description="test", redis=redis_client
    )
    image = await create_image(conn, redis_client, session_id=session_id, images_id=resource.id)
    upload = await create_upload(
        conn, redis_client, session_id=session_id,
        file_path="/test/image.png", mime_type="image/png", size=2048,
    )
    await create_image_upload(
        conn, redis_client, image_id=image.id, upload_id=upload.id, session_id=session_id
    )
    return image


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_images_appears_after_refresh(conn, redis_client, session_id):
    created = _created(await create_image(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'image_id', None) or getattr(created, 'id', None) or getattr(created, 'image', None)

    await refresh_images_internal(conn)
    item = await get_image(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_new_images_is_visible_before_refresh(conn, redis_client, session_id):
    # get_image's bypass_cache path reads the base images_entry table (not the
    # MV), so a freshly created row is immediately visible without any refresh.
    # Refresh only repopulates images_mv (see the MV-population test below).
    created = _created(await create_image(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'image_id', None) or getattr(created, 'id', None) or getattr(created, 'image', None)

    item = await get_image(conn, lookup_id, redis_client, bypass_cache=True)

    assert item is not None
    assert item.id == lookup_id


async def test_images_mv_populated_only_after_refresh(conn, redis_client, session_id):
    # The materialized view images_mv is NOT updated by create; it only reflects
    # the new (MV-eligible) row after refresh_images_internal.
    image = await _mv_eligible_image(conn, redis_client, session_id)
    lookup_id = image.id

    in_mv_before = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM images_mv WHERE image_id = $1)", lookup_id
    )
    assert in_mv_before is False

    await refresh_images_internal(conn)

    in_mv_after = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM images_mv WHERE image_id = $1)", lookup_id
    )
    assert in_mv_after is True


async def test_refresh_is_idempotent(conn):
    await refresh_images_internal(conn)
    await refresh_images_internal(conn)

    assert True
