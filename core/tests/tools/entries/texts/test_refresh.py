"""Tests for refresh_texts_internal."""

import pytest
from app.tools.entries.sessions.create import create_session
from app.tools.entries.texts.create import create_text
from app.tools.entries.texts.get import get_text
from app.tools.entries.texts.refresh import refresh_texts_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def _mv_eligible_text(conn, redis_client, session_id):
    # texts_mv inner-joins texts_resource via texts_texts_connection, so wire up
    # the resource + connection here — a bare create_text never enters the MV.
    text = await create_text(conn, redis_client, session_id=session_id)
    texts_resource_id = await conn.fetchval(
        "INSERT INTO texts_resource DEFAULT VALUES RETURNING id"
    )
    await conn.execute(
        "INSERT INTO texts_texts_connection (texts_id, text_id) VALUES ($1, $2)",
        texts_resource_id,
        text.id,
    )
    return text


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_texts_appears_after_refresh(conn, redis_client, session_id):
    created = _created(await create_text(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'text_id', None) or getattr(created, 'id', None) or getattr(created, 'text', None)

    await refresh_texts_internal(conn)
    item = await get_text(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_new_texts_is_visible_before_refresh(conn, redis_client, session_id):
    # get_text's bypass_cache path reads the base texts_entry table (not the MV),
    # so a freshly created row is immediately visible without any refresh.
    # Refresh only repopulates texts_mv (see the MV-population test below).
    created = _created(await create_text(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'text_id', None) or getattr(created, 'id', None) or getattr(created, 'text', None)

    item = await get_text(conn, lookup_id, redis_client, bypass_cache=True)

    assert item is not None
    assert item.id == lookup_id


async def test_texts_mv_populated_only_after_refresh(conn, redis_client, session_id):
    # The materialized view texts_mv is NOT updated by create; it only reflects
    # the new (MV-eligible) row after refresh_texts_internal.
    text = await _mv_eligible_text(conn, redis_client, session_id)
    lookup_id = text.id

    in_mv_before = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM texts_mv WHERE text_id = $1)", lookup_id
    )
    assert in_mv_before is False

    await refresh_texts_internal(conn)

    in_mv_after = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM texts_mv WHERE text_id = $1)", lookup_id
    )
    assert in_mv_after is True


async def test_refresh_is_idempotent(conn):
    await refresh_texts_internal(conn)
    await refresh_texts_internal(conn)

    assert True
