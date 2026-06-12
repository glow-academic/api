"""Tests for setting_drafts search."""

from uuid import UUID

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.sessions.create import create_session
from app.tools.entries.setting_drafts.create import create_setting_draft
from app.tools.entries.setting_drafts.search import search_setting_drafts

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    return session, group


async def test_search_finds_created(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    result = await create_setting_draft(conn, redis_client, session_id=session.id)

    items = await search_setting_drafts(conn, redis_client, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_search_filters_by_session(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    result = await create_setting_draft(conn, redis_client, session_id=session.id)

    items = await search_setting_drafts(conn, redis_client, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_search_returns_connections(conn, redis_client, profile_id, name_id: UUID):
    session, group = await _setup(conn, redis_client, profile_id)

    result = await create_setting_draft(
        conn,
        redis_client, session_id=session.id,
        name_ids=[name_id],
    )

    items = await search_setting_drafts(conn, redis_client, session_ids=[session.id])

    match = [i for i in items if i.id == result.id]
    assert len(match) == 1
    assert name_id in match[0].name_ids


async def test_search_pagination(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    await create_setting_draft(conn, redis_client, session_id=session.id)
    await create_setting_draft(conn, redis_client, session_id=session.id)

    items = await search_setting_drafts(conn, redis_client, session_ids=[session.id], limit=1)

    assert len(items) == 1


# ── D1 read-IDOR: session-scope is mandatory and fail-closed ───────────────


async def test_search_excludes_other_session(conn, redis_client, profile_id):
    """ALLOW/DENY: a caller sees ONLY their own session's setting drafts.

    Another session's drafts must NOT be returned when scoping to one session.
    """
    mine, _ = await _setup(conn, redis_client, profile_id)
    theirs, _ = await _setup(conn, redis_client, profile_id)

    my_draft = await create_setting_draft(conn, redis_client, session_id=mine.id)
    their_draft = await create_setting_draft(conn, redis_client, session_id=theirs.id)

    items = await search_setting_drafts(conn, redis_client, session_ids=[mine.id])
    ids = [item.id for item in items]

    assert my_draft.id in ids
    assert their_draft.id not in ids


async def test_search_fail_closed_no_session_scope(conn, redis_client, profile_id):
    """DENY/fail-closed: with NO session scope the search returns nothing.

    Asserts the historical TRUE-collapse (every user's setting drafts leaking)
    is gone — an unscoped call must yield zero rows, never the whole table.
    """
    session, _ = await _setup(conn, redis_client, profile_id)
    await create_setting_draft(conn, redis_client, session_id=session.id)

    # No session_ids at all -> fail closed (default arg is None).
    assert await search_setting_drafts(conn, redis_client) == []
    # Explicit None -> fail closed.
    assert await search_setting_drafts(conn, redis_client, session_ids=None) == []
    # Empty list -> fail closed (no "all sessions" interpretation).
    assert await search_setting_drafts(conn, redis_client, session_ids=[]) == []


async def test_search_profile_ids_alone_does_not_unscope(conn, redis_client, profile_id):
    """DENY: passing only profile_ids (no session scope) still returns nothing.

    setting_drafts has no profiles-connection table, so profile_ids is not a
    usable scope here; it must not re-open the leak.
    """
    session, _ = await _setup(conn, redis_client, profile_id)
    await create_setting_draft(conn, redis_client, session_id=session.id)

    items = await search_setting_drafts(conn, redis_client, profile_ids=[profile_id])
    assert items == []
