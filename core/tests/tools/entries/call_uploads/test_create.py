"""Tests for create_call_upload."""

from uuid import uuid4

import pytest

from app.tools.entries.call_uploads.create import create_call_upload
from app.tools.entries.call_uploads.get import get_call_upload
from app.tools.entries.call_uploads.search import search_call_uploads
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    upload = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/response.json",
        mime_type="application/json",
        size=512,
    )
    return session, call, upload


async def test_creates_call_upload_entry(conn, redis_client, profile_id):
    session, call, upload = await _deps(conn, redis_client, profile_id)
    result = await create_call_upload(
        conn, redis_client, call_id=call.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_create_sets_link_fields(conn, redis_client, profile_id):
    """Created row carries the call/upload/session links and defaults."""
    session, call, upload = await _deps(conn, redis_client, profile_id)
    result = await create_call_upload(
        conn, redis_client, call_id=call.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_call_upload(conn, result.id, redis_client)

    assert row is not None
    assert row.id == result.id
    assert row.call_id == call.id
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
    session, call, upload = await _deps(conn, redis_client, profile_id)
    result = await create_call_upload(
        conn, redis_client, call_id=call.id, upload_id=upload.id, session_id=session.id
    )

    cached = await get_call_upload(conn, result.id, redis_client)
    from_db = await get_call_upload(conn, result.id, redis_client, bypass_cache=True)

    assert cached is not None
    assert from_db is not None
    assert cached.id == from_db.id
    assert cached.call_id == from_db.call_id
    assert cached.upload_id == from_db.upload_id
    assert cached.session_id == from_db.session_id
    assert cached.active == from_db.active
    assert cached.mcp == from_db.mcp
    assert cached.generated == from_db.generated
    assert cached.created_at == from_db.created_at


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session, call, upload = await _deps(conn, redis_client, profile_id)
    result = await create_call_upload(
        conn,
        redis_client,
        call_id=call.id,
        upload_id=upload.id,
        session_id=session.id,
        mcp=True,
    )

    row = await get_call_upload(conn, result.id, redis_client)

    assert row is not None
    assert row.mcp is True


async def test_soft_create_is_inactive(conn, redis_client, profile_id):
    """soft=True yields an inactive row (active is the inverse of soft)."""
    session, call, upload = await _deps(conn, redis_client, profile_id)
    result = await create_call_upload(
        conn,
        redis_client,
        call_id=call.id,
        upload_id=upload.id,
        session_id=session.id,
        soft=True,
    )

    row = await get_call_upload(conn, result.id, redis_client, bypass_cache=True)

    assert row is not None
    assert row.active is False


async def test_honors_explicit_id(conn, redis_client, profile_id):
    """An explicit id is used verbatim (idempotent-create primitive)."""
    session, call, upload = await _deps(conn, redis_client, profile_id)
    explicit_id = uuid4()
    result = await create_call_upload(
        conn,
        redis_client,
        call_id=call.id,
        upload_id=upload.id,
        session_id=session.id,
        id=explicit_id,
    )

    assert result.id == explicit_id
    row = await get_call_upload(conn, explicit_id, redis_client)
    assert row is not None
    assert row.id == explicit_id


async def test_created_entry_is_searchable(conn, redis_client, profile_id):
    """A freshly created active entry is found by search on its call link."""
    session, call, upload = await _deps(conn, redis_client, profile_id)
    result = await create_call_upload(
        conn, redis_client, call_id=call.id, upload_id=upload.id, session_id=session.id
    )

    found = await search_call_uploads(
        conn, redis_client, call_ids=[call.id], bypass_cache=True
    )

    assert any(r.id == result.id for r in found)
