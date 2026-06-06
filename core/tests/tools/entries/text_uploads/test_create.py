"""Tests for create_text_upload."""

from uuid import uuid4

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.text_uploads.get import get_text_upload
from app.tools.entries.text_uploads.search import search_text_uploads
from app.tools.entries.texts.create import create_text
from app.tools.entries.texts.search import search_texts
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    text = await create_text(conn, redis_client, session_id=session.id)
    upload = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )
    return session, text, upload


async def test_creates_text_upload_entry(conn, redis_client, profile_id):
    session, text, upload = await _deps(conn, redis_client, profile_id)
    result = await create_text_upload(
        conn, redis_client, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_create_sets_link_fields(conn, redis_client, profile_id):
    """Created junction row carries the text/upload/session links and defaults."""
    session, text, upload = await _deps(conn, redis_client, profile_id)
    result = await create_text_upload(
        conn, redis_client, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_text_upload(conn, result.id, redis_client)

    assert row is not None
    assert row.id == result.id
    assert row.text_id == text.id
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
    session, text, upload = await _deps(conn, redis_client, profile_id)
    result = await create_text_upload(
        conn, redis_client, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    cached = await get_text_upload(conn, result.id, redis_client)
    from_db = await get_text_upload(
        conn, result.id, redis_client, bypass_cache=True
    )

    assert cached is not None
    assert from_db is not None
    assert cached.id == from_db.id
    assert cached.text_id == from_db.text_id
    assert cached.upload_id == from_db.upload_id
    assert cached.session_id == from_db.session_id
    assert cached.active == from_db.active
    assert cached.mcp == from_db.mcp
    assert cached.generated == from_db.generated
    assert cached.created_at == from_db.created_at


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session, text, upload = await _deps(conn, redis_client, profile_id)
    result = await create_text_upload(
        conn,
        redis_client,
        text_id=text.id,
        upload_id=upload.id,
        session_id=session.id,
        mcp=True,
    )

    row = await get_text_upload(conn, result.id, redis_client)

    assert row is not None
    assert row.mcp is True


async def test_soft_create_is_inactive(conn, redis_client, profile_id):
    """soft=True yields an inactive junction row."""
    session, text, upload = await _deps(conn, redis_client, profile_id)
    result = await create_text_upload(
        conn,
        redis_client,
        text_id=text.id,
        upload_id=upload.id,
        session_id=session.id,
        soft=True,
    )

    row = await get_text_upload(conn, result.id, redis_client, bypass_cache=True)

    assert row is not None
    assert row.active is False


async def test_honors_explicit_id(conn, redis_client, profile_id):
    """An explicit id is used verbatim (idempotent-create primitive)."""
    session, text, upload = await _deps(conn, redis_client, profile_id)
    explicit_id = uuid4()
    result = await create_text_upload(
        conn,
        redis_client,
        text_id=text.id,
        upload_id=upload.id,
        session_id=session.id,
        id=explicit_id,
    )

    assert result.id == explicit_id
    row = await get_text_upload(conn, explicit_id, redis_client)
    assert row is not None
    assert row.id == explicit_id


async def test_created_entry_is_searchable(conn, redis_client, profile_id):
    """A freshly created junction is found by search on its text id."""
    session, text, upload = await _deps(conn, redis_client, profile_id)
    result = await create_text_upload(
        conn, redis_client, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    found = await search_text_uploads(conn, redis_client, text_ids=[text.id])

    match = next((r for r in found if r.id == result.id), None)
    assert match is not None
    assert match.text_id == text.id
    assert match.upload_id == upload.id


async def test_create_invalidates_parent_text_cache(conn, redis_client, profile_id):
    """Linking an upload busts the parent text's stale write-back cache row.

    #163/#105 stale-partial-cache regression. ``create_text`` seeds the
    ``texts`` write-back cache with ``upload_id=None`` (the denormalized
    upload columns are blank until a ``text_uploads`` row links in). The
    hedged ``search_texts`` prefers the cached row over the MV, so if
    ``create_text_upload`` did NOT invalidate that cache row, a search after
    linking would keep returning the stale ``upload_id=None`` shape forever.

    This asserts the post-link search never surfaces the text with a blank
    ``upload_id`` — which is exactly what regresses if the ``invalidate_row``
    call in ``create_text_upload`` is dropped.
    """
    session, text, upload = await _deps(conn, redis_client, profile_id)

    # Pre-link: the cached text row has the blank upload denorm fields.
    before = await search_texts(conn, redis_client, text_ids=[text.id])
    stale = next((r for r in before if r.text_id == text.id), None)
    assert stale is not None
    assert stale.upload_id is None  # the partial cache row we must not keep serving

    await create_text_upload(
        conn, redis_client, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    # Post-link: the stale partial cache row must be gone. The hedged search
    # must NOT return the text still claiming upload_id=None.
    after = await search_texts(conn, redis_client, text_ids=[text.id])
    assert not any(
        r.text_id == text.id and r.upload_id is None for r in after
    ), "create_text_upload must invalidate the parent text cache (#163 pattern)"
