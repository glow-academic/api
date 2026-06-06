"""Tests for create_upload."""

from uuid import uuid4

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.uploads.get import get_upload
from app.tools.entries.uploads.search import search_uploads

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def test_creates_upload_entry(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )

    assert result.id is not None


async def test_create_sets_all_fields(conn, redis_client, profile_id):
    """Created row carries the session link, file metadata, and defaults."""
    session = await _session(conn, redis_client, profile_id)
    result = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )

    upload = await get_upload(conn, result.id, redis_client)

    assert upload is not None
    assert upload.id == result.id
    assert upload.session_id == session.id
    assert upload.file_path == "test/file.txt"
    assert upload.mime_type == "text/plain"
    assert upload.size == 1024
    assert upload.active is True
    assert upload.mcp is False
    assert upload.generated is True


async def test_create_cache_matches_db(conn, redis_client, profile_id):
    """The row written back to cache on create matches the persisted DB row.

    Guards against a #163-class cache-coherence bug: create writes a synthetic
    row to Redis via write_back_row, and get serves it without touching the DB.
    If that synthetic row drifted from what was actually persisted, the cached
    read and the bypass-cache (DB) read would disagree.
    """
    session = await _session(conn, redis_client, profile_id)
    result = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/coherent.pdf",
        mime_type="application/pdf",
        size=2048,
    )

    cached = await get_upload(conn, result.id, redis_client)
    from_db = await get_upload(conn, result.id, redis_client, bypass_cache=True)

    assert cached is not None
    assert from_db is not None
    assert cached.id == from_db.id
    assert cached.session_id == from_db.session_id
    assert cached.file_path == from_db.file_path
    assert cached.mime_type == from_db.mime_type
    assert cached.size == from_db.size
    assert cached.active == from_db.active
    assert cached.mcp == from_db.mcp
    assert cached.generated == from_db.generated
    assert cached.created_at == from_db.created_at


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=512,
        mcp=True,
    )

    upload = await get_upload(conn, result.id, redis_client)

    assert upload is not None
    assert upload.mcp is True


async def test_soft_create_is_inactive(conn, redis_client, profile_id):
    """soft=True yields an inactive row (active is the inverse of soft)."""
    session = await _session(conn, redis_client, profile_id)
    result = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/soft.txt",
        mime_type="text/plain",
        size=64,
        soft=True,
    )

    row = await get_upload(conn, result.id, redis_client, bypass_cache=True)

    assert row is not None
    assert row.active is False


async def test_honors_explicit_id(conn, redis_client, profile_id):
    """An explicit id is used verbatim (idempotent-create primitive)."""
    session = await _session(conn, redis_client, profile_id)
    explicit_id = uuid4()
    result = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/explicit.txt",
        mime_type="text/plain",
        size=8,
        id=explicit_id,
    )

    assert result.id == explicit_id
    row = await get_upload(conn, explicit_id, redis_client)
    assert row is not None
    assert row.id == explicit_id


async def test_created_entry_is_searchable(conn, redis_client, profile_id):
    """A freshly created entry is found by search on its upload id."""
    session = await _session(conn, redis_client, profile_id)
    result = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/searchable.txt",
        mime_type="text/plain",
        size=16,
    )

    found = await search_uploads(conn, redis_client, upload_ids=[result.id])

    match = next((r for r in found if r.upload_id == result.id), None)
    assert match is not None
    assert match.file_path == "test/searchable.txt"
    assert match.mime_type == "text/plain"
    assert match.size == 16
