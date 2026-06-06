"""Tests for create_message_upload."""

from uuid import uuid4

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.message_uploads.get import get_message_upload
from app.tools.entries.message_uploads.search import search_message_uploads
from app.tools.entries.messages.create import create_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.utils.cache.hedged_row import read_back_row

pytestmark = pytest.mark.asyncio


async def _deps(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id
    )
    message = await create_message(
        conn, redis_client, run_id=run.id, role="assistant"
    )
    upload = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/attachment.pdf",
        mime_type="application/pdf",
        size=2048,
    )
    return session, message, upload


async def test_creates_message_upload_entry(conn, redis_client, profile_id):
    session, message, upload = await _deps(conn, redis_client, profile_id)
    result = await create_message_upload(
        conn, redis_client, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_create_sets_link_fields(conn, redis_client, profile_id):
    """Created junction row carries the message/upload/session links and defaults."""
    session, message, upload = await _deps(conn, redis_client, profile_id)
    result = await create_message_upload(
        conn, redis_client, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_message_upload(conn, result.id, redis_client)

    assert row is not None
    assert row.id == result.id
    assert row.message_id == message.id
    assert row.upload_id == upload.id
    assert row.session_id == session.id
    assert row.active is True
    assert row.mcp is False
    assert row.generated is True


async def test_create_cache_matches_db(conn, redis_client, profile_id):
    """The junction cache row written on create matches the persisted DB row.

    #163-class guard against the synthetic write-back row drifting from the
    real row that get serves on a cache miss.
    """
    session, message, upload = await _deps(conn, redis_client, profile_id)
    result = await create_message_upload(
        conn, redis_client, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    cached = await get_message_upload(conn, result.id, redis_client)
    from_db = await get_message_upload(
        conn, result.id, redis_client, bypass_cache=True
    )

    assert cached is not None
    assert from_db is not None
    assert cached.id == from_db.id
    assert cached.message_id == from_db.message_id
    assert cached.upload_id == from_db.upload_id
    assert cached.session_id == from_db.session_id
    assert cached.active == from_db.active
    assert cached.mcp == from_db.mcp
    assert cached.generated == from_db.generated
    assert cached.created_at == from_db.created_at


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session, message, upload = await _deps(conn, redis_client, profile_id)
    result = await create_message_upload(
        conn,
        redis_client,
        message_id=message.id,
        upload_id=upload.id,
        session_id=session.id,
        mcp=True,
    )

    row = await get_message_upload(conn, result.id, redis_client)

    assert row is not None
    assert row.mcp is True


async def test_soft_create_is_inactive(conn, redis_client, profile_id):
    """soft=True yields an inactive junction row."""
    session, message, upload = await _deps(conn, redis_client, profile_id)
    result = await create_message_upload(
        conn,
        redis_client,
        message_id=message.id,
        upload_id=upload.id,
        session_id=session.id,
        soft=True,
    )

    row = await get_message_upload(conn, result.id, redis_client, bypass_cache=True)

    assert row is not None
    assert row.active is False


async def test_honors_explicit_id(conn, redis_client, profile_id):
    """An explicit id is used verbatim (idempotent-create primitive)."""
    session, message, upload = await _deps(conn, redis_client, profile_id)
    explicit_id = uuid4()
    result = await create_message_upload(
        conn,
        redis_client,
        message_id=message.id,
        upload_id=upload.id,
        session_id=session.id,
        id=explicit_id,
    )

    assert result.id == explicit_id
    row = await get_message_upload(conn, explicit_id, redis_client)
    assert row is not None
    assert row.id == explicit_id


async def test_created_entry_is_searchable(conn, redis_client, profile_id):
    """A freshly created junction is found by search on its message id."""
    session, message, upload = await _deps(conn, redis_client, profile_id)
    result = await create_message_upload(
        conn, redis_client, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    found = await search_message_uploads(
        conn, redis_client, message_ids=[message.id]
    )

    match = next((r for r in found if r.id == result.id), None)
    assert match is not None
    assert match.message_id == message.id
    assert match.upload_id == upload.id


async def test_create_invalidates_parent_message_cache(conn, redis_client, profile_id):
    """Linking an upload busts the parent message's stale write-back cache row.

    #163/#105 stale-partial-cache regression. ``create_message`` seeds the
    ``messages`` write-back cache with empty ``*_ids`` arrays (the upload links
    are blank until a junction row links in). If ``create_message_upload`` did
    NOT invalidate that cached row, the hedged ``search_messages`` would keep
    serving the stale partial row instead of falling through to the MV.

    Asserts the parent message's cache key is present after ``create_message``
    and gone after the junction write — exactly what regresses if the
    ``invalidate_row(redis, "messages", message_id)`` call is dropped.
    """
    session, message, upload = await _deps(conn, redis_client, profile_id)

    # create_message seeded the parent message's write-back cache row.
    seeded = await read_back_row(redis_client, "messages", message.id)
    assert seeded is not None
    assert seeded.get("file_ids") == []  # the partial shape we must not keep serving

    await create_message_upload(
        conn, redis_client, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    # The junction write must have invalidated the parent message cache row.
    after = await read_back_row(redis_client, "messages", message.id)
    assert after is None, (
        "create_message_upload must invalidate the parent message cache (#163 pattern)"
    )
