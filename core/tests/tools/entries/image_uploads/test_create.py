"""Tests for create_image_upload."""

from uuid import uuid4

import pytest

from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.image_uploads.get import get_image_upload
from app.tools.entries.image_uploads.search import search_image_uploads
from app.tools.entries.images.create import create_image
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    image = await create_image(conn, redis_client, session_id=session.id)
    upload = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/photo.jpg",
        mime_type="image/jpeg",
        size=4096,
    )
    return session, image, upload


async def test_creates_image_upload_entry(conn, redis_client, profile_id):
    session, image, upload = await _deps(conn, redis_client, profile_id)
    result = await create_image_upload(
        conn, redis_client, image_id=image.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_create_sets_link_fields(conn, redis_client, profile_id):
    """Created row carries the image/upload/session links and defaults."""
    session, image, upload = await _deps(conn, redis_client, profile_id)
    result = await create_image_upload(
        conn, redis_client, image_id=image.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_image_upload(conn, result.id, redis_client)

    assert row is not None
    assert row.id == result.id
    assert row.image_id == image.id
    assert row.upload_id == upload.id
    assert row.session_id == session.id
    assert row.active is True
    assert row.mcp is False
    assert row.generated is True


async def test_create_cache_matches_db(conn, redis_client, profile_id):
    """The row written back to cache on create matches the persisted DB row.

    Guards against a #163-class cache-coherence bug: create writes a synthetic
    row to Redis via write_back_row, and get serves it without touching the DB.
    If that synthetic row drifted from what was actually persisted, the cached
    read and the bypass-cache (DB) read would disagree.
    """
    session, image, upload = await _deps(conn, redis_client, profile_id)
    result = await create_image_upload(
        conn, redis_client, image_id=image.id, upload_id=upload.id, session_id=session.id
    )

    cached = await get_image_upload(conn, result.id, redis_client)
    from_db = await get_image_upload(conn, result.id, redis_client, bypass_cache=True)

    assert cached is not None
    assert from_db is not None
    assert cached.id == from_db.id
    assert cached.image_id == from_db.image_id
    assert cached.upload_id == from_db.upload_id
    assert cached.session_id == from_db.session_id
    assert cached.active == from_db.active
    assert cached.mcp == from_db.mcp
    assert cached.generated == from_db.generated
    assert cached.created_at == from_db.created_at


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session, image, upload = await _deps(conn, redis_client, profile_id)
    result = await create_image_upload(
        conn,
        redis_client,
        image_id=image.id,
        upload_id=upload.id,
        session_id=session.id,
        mcp=True,
    )

    row = await get_image_upload(conn, result.id, redis_client)

    assert row is not None
    assert row.mcp is True


async def test_soft_create_is_inactive(conn, redis_client, profile_id):
    """soft=True yields an inactive row (active is the inverse of soft)."""
    session, image, upload = await _deps(conn, redis_client, profile_id)
    result = await create_image_upload(
        conn,
        redis_client,
        image_id=image.id,
        upload_id=upload.id,
        session_id=session.id,
        soft=True,
    )

    row = await get_image_upload(conn, result.id, redis_client, bypass_cache=True)

    assert row is not None
    assert row.active is False


async def test_honors_explicit_id(conn, redis_client, profile_id):
    """An explicit id is used verbatim (idempotent-create primitive)."""
    session, image, upload = await _deps(conn, redis_client, profile_id)
    explicit_id = uuid4()
    result = await create_image_upload(
        conn,
        redis_client,
        image_id=image.id,
        upload_id=upload.id,
        session_id=session.id,
        id=explicit_id,
    )

    assert result.id == explicit_id
    row = await get_image_upload(conn, explicit_id, redis_client)
    assert row is not None
    assert row.id == explicit_id


async def test_created_entry_is_searchable(conn, redis_client, profile_id):
    """A freshly created active entry is found by search on its image link."""
    session, image, upload = await _deps(conn, redis_client, profile_id)
    result = await create_image_upload(
        conn, redis_client, image_id=image.id, upload_id=upload.id, session_id=session.id
    )

    found = await search_image_uploads(
        conn, redis_client, image_ids=[image.id], bypass_cache=True
    )

    assert any(r.id == result.id for r in found)
