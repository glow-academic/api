"""Tests for create_upload_completion."""

from uuid import uuid4

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.upload_completion.create import (
    create_upload_completion,
)
from app.tools.entries.upload_completion.get import get_upload_completion
from app.tools.entries.upload_completion.search import (
    search_upload_completions,
)
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _upload(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    upload = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )
    return session, upload


async def test_creates_upload_completion_entry(conn, redis_client, profile_id):
    session, upload = await _upload(conn, redis_client, profile_id)
    result = await create_upload_completion(
        conn, redis_client, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_create_sets_fields_and_defaults(conn, redis_client, profile_id):
    """Created row carries the upload/session links and completion defaults."""
    session, upload = await _upload(conn, redis_client, profile_id)
    result = await create_upload_completion(
        conn, redis_client, upload_id=upload.id, session_id=session.id
    )

    row = await get_upload_completion(conn, result.id, redis_client)

    assert row is not None
    assert row.id == result.id
    assert row.upload_id == upload.id
    assert row.session_id == session.id
    assert row.active is True
    assert row.mcp is False
    assert row.generated is True
    assert row.stop is False
    assert row.error is False
    assert row.message == ""


async def test_create_persists_stop_error_message(conn, redis_client, profile_id):
    """The stop/error/message payload fields round-trip through create→get."""
    session, upload = await _upload(conn, redis_client, profile_id)
    result = await create_upload_completion(
        conn,
        redis_client,
        upload_id=upload.id,
        session_id=session.id,
        stop=True,
        error=True,
        message="boom",
    )

    row = await get_upload_completion(conn, result.id, redis_client, bypass_cache=True)

    assert row is not None
    assert row.stop is True
    assert row.error is True
    assert row.message == "boom"


async def test_create_cache_matches_db(conn, redis_client, profile_id):
    """The row written back to cache on create matches the persisted DB row.

    Guards against a #163-class cache-coherence bug: create writes a synthetic
    row to Redis via write_back_row, and get serves it without touching the DB.
    If that synthetic row drifted from what was actually persisted, the cached
    read and the bypass-cache (DB) read would disagree.
    """
    session, upload = await _upload(conn, redis_client, profile_id)
    result = await create_upload_completion(
        conn,
        redis_client,
        upload_id=upload.id,
        session_id=session.id,
        stop=True,
        error=False,
        message="done",
    )

    cached = await get_upload_completion(conn, result.id, redis_client)
    from_db = await get_upload_completion(
        conn, result.id, redis_client, bypass_cache=True
    )

    assert cached is not None
    assert from_db is not None
    assert cached.id == from_db.id
    assert cached.upload_id == from_db.upload_id
    assert cached.session_id == from_db.session_id
    assert cached.active == from_db.active
    assert cached.mcp == from_db.mcp
    assert cached.generated == from_db.generated
    assert cached.stop == from_db.stop
    assert cached.error == from_db.error
    assert cached.message == from_db.message
    assert cached.created_at == from_db.created_at


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session, upload = await _upload(conn, redis_client, profile_id)
    result = await create_upload_completion(
        conn,
        redis_client,
        upload_id=upload.id,
        session_id=session.id,
        mcp=True,
    )

    row = await get_upload_completion(conn, result.id, redis_client)

    assert row is not None
    assert row.mcp is True


async def test_honors_explicit_id(conn, redis_client, profile_id):
    """An explicit id is used verbatim (idempotent-create primitive)."""
    session, upload = await _upload(conn, redis_client, profile_id)
    explicit_id = uuid4()
    result = await create_upload_completion(
        conn,
        redis_client,
        upload_id=upload.id,
        session_id=session.id,
        id=explicit_id,
    )

    assert result.id == explicit_id
    row = await get_upload_completion(conn, explicit_id, redis_client)
    assert row is not None
    assert row.id == explicit_id


async def test_duplicate_completion_is_idempotent(conn, redis_client, profile_id):
    """C1-B: re-completing an upload refreshes the row in place, no 2nd row."""
    session, upload = await _upload(conn, redis_client, profile_id)

    first = await create_upload_completion(
        conn, redis_client, upload_id=upload.id, session_id=session.id, message="one"
    )
    second = await create_upload_completion(
        conn, redis_client, upload_id=upload.id, session_id=session.id, message="two"
    )

    rows = await conn.fetch(
        "SELECT id, active, message FROM upload_completion_entry WHERE upload_id = $1",
        upload.id,
    )
    assert len(rows) == 1
    assert rows[0]["active"] is True
    assert first.id == second.id
    # The in-place update reflects the latest payload.
    assert rows[0]["message"] == "two"


async def test_created_entry_is_searchable(conn, redis_client, profile_id):
    """A freshly created entry is found by search on its upload link."""
    session, upload = await _upload(conn, redis_client, profile_id)
    result = await create_upload_completion(
        conn, redis_client, upload_id=upload.id, session_id=session.id
    )

    found = await search_upload_completions(
        conn, redis_client, upload_ids=[upload.id], bypass_mv=True, bypass_cache=True
    )

    assert any(r.id == result.id for r in found)
