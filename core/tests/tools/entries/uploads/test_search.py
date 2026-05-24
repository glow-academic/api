"""Tests for search_uploads."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.uploads.search import search_uploads

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    upload = await create_upload(
        conn,
        redis_client, session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )
    return upload


async def test_finds_created_entry(conn, redis_client, profile_id):
    upload = await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW uploads_mv")

    items = await search_uploads(conn, redis_client, upload_ids=[upload.id])

    ids = [item.upload_id for item in items]
    assert upload.id in ids


async def test_filters_by_upload_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW uploads_mv")

    items = await search_uploads(conn, redis_client, upload_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    upload = await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW uploads_mv")

    items = await search_uploads(conn, redis_client, upload_ids=[upload.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW uploads_mv")

    items = await search_uploads(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    upload = await _setup(conn, redis_client, profile_id)

    items = await search_uploads(conn, redis_client, upload_ids=[upload.id], bypass_mv=True)

    ids = [item.upload_id for item in items]
    assert upload.id in ids
