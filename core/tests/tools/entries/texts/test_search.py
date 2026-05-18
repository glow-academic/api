"""Tests for search_texts."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.sessions.create import create_session
from app.tools.entries.texts.create import create_text
from app.tools.entries.texts.search import search_texts

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    text = await create_text(conn, session_id=session.id)
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


async def test_finds_created_entry(conn, profile_id):
    text, _ = await _setup(conn, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, text_ids=[text.id])

    ids = [item.text_id for item in items]
    assert text.id in ids


async def test_filters_by_text_id(conn, profile_id):
    await _setup(conn, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, text_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, profile_id):
    text, _ = await _setup(conn, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn, text_ids=[text.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW texts_mv")

    items = await search_texts(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    text, _ = await _setup(conn, profile_id)

    items = await search_texts(conn, text_ids=[text.id], bypass_mv=True)

    ids = [item.text_id for item in items]
    assert text.id in ids
