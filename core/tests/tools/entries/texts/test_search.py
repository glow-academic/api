"""Tests for search_texts."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.sessions.create import create_session
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.texts.create import create_text
from app.tools.entries.texts.search import search_texts
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    text = await create_text(conn, redis_client, session_id=session.id)
    # texts_mv requires: texts_resource + texts_texts_connection + texts_entry
    texts_resource_id = await conn.fetchval(
        "INSERT INTO texts_resource DEFAULT VALUES RETURNING id"
    )
    await conn.execute(
        "INSERT INTO texts_texts_connection (texts_id, text_id) VALUES ($1, $2)",
        texts_resource_id,
        text.id,
    )
    return text, texts_resource_id


async def _setup_with_upload(conn, redis_client, profile_id):
    """Full resource->entry->upload chain, mirroring how the document viewer's
    seeded texts resolve to a file on disk."""
    text, texts_resource_id = await _setup(conn, redis_client, profile_id)
    session = await create_session(conn, redis_client, profile_id=profile_id)
    upload = await create_upload(
        conn, redis_client, session.id, "policy.txt", "text/plain", 3
    )
    await create_text_upload(conn, redis_client, text.id, upload.id, session.id)
    return text, texts_resource_id, upload.id


async def test_finds_created_entry(conn, redis_client, profile_id):
    text, _ = await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, redis_client, text_ids=[text.id])

    ids = [item.text_id for item in items]
    assert text.id in ids


async def test_filters_by_text_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, redis_client, text_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    text, _ = await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, redis_client, text_ids=[text.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    text, _ = await _setup(conn, redis_client, profile_id)

    items = await search_texts(conn, redis_client, text_ids=[text.id], bypass_mv=True)

    ids = [item.text_id for item in items]
    assert text.id in ids


async def test_filters_by_texts_resource_id(conn, redis_client, profile_id):
    """Defect #1: the document viewer holds the texts-RESOURCE id, not the
    ENTRY id. ``texts_ids`` must filter on texts_mv.texts_id (the resource)."""
    text, texts_resource_id = await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, redis_client, texts_ids=[texts_resource_id])

    resource_ids = [item.texts_id for item in items]
    assert texts_resource_id in resource_ids
    # And the matched row carries the ENTRY id, confirming resource->entry map.
    assert text.id in [item.text_id for item in items]


async def test_resource_id_resolves_to_upload(conn, redis_client, profile_id):
    """Defect #1 end-to-end id-model: a texts-RESOURCE id resolves through the
    new ``texts_ids`` filter to the upload_id (was a 404 via search_text_uploads,
    which keys on the ENTRY id)."""
    text, texts_resource_id, upload_id = await _setup_with_upload(
        conn, redis_client, profile_id
    )
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, redis_client, texts_ids=[texts_resource_id], limit=1)

    assert items, "resource id must resolve via texts_mv.texts_id"
    assert items[0].upload_id == upload_id


async def test_texts_resource_id_does_not_match_entry_id(conn, redis_client, profile_id):
    """The bug: passing the ENTRY id as a resource filter must NOT match — proving
    the two id spaces are distinct (and that the old entry-keyed lookup 404'd)."""
    text, texts_resource_id = await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, redis_client, texts_ids=[text.id])

    assert items == []
