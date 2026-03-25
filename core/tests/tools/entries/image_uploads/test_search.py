"""Tests for image_uploads search."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.image_uploads.search import search_image_uploads
from app.tools.entries.images.create import create_image
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    image = await create_image(conn, session_id=session.id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/photo.jpg",
        mime_type="image/jpeg",
        size=4096,
    )
    return session, image, upload


async def test_search_finds_created(conn, profile_id):
    session, image, upload = await _deps(conn, profile_id)
    await create_image_upload(
        conn, image_id=image.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_image_uploads(conn, image_ids=[image.id])

    assert len(results) == 1
    assert results[0].image_id == image.id
    assert results[0].upload_id == upload.id


async def test_search_filters_by_image_id(conn, profile_id):
    session, image, upload = await _deps(conn, profile_id)
    await create_image_upload(
        conn, image_id=image.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_image_uploads(conn, image_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_filters_by_upload_id(conn, profile_id):
    session, image, upload = await _deps(conn, profile_id)
    await create_image_upload(
        conn, image_id=image.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_image_uploads(conn, upload_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_pagination(conn, profile_id):
    session, image, upload1 = await _deps(conn, profile_id)
    upload2 = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/photo2.jpg",
        mime_type="image/jpeg",
        size=4096,
    )
    await create_image_upload(
        conn, image_id=image.id, upload_id=upload1.id, session_id=session.id
    )
    await create_image_upload(
        conn, image_id=image.id, upload_id=upload2.id, session_id=session.id
    )

    results = await search_image_uploads(conn, image_ids=[image.id], limit=1)

    assert len(results) == 1
