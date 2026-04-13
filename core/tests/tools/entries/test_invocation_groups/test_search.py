"""Tests for search_test_invocation_groups."""

import pytest
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation_groups.create import (
    create_test_invocation_groups,
)
from app.tools.entries.test_invocation_groups.get import (
    get_test_invocation_groups,
)
from app.tools.entries.test_invocation_groups.refresh import (
    refresh_test_invocation_groups,
)
from app.tools.entries.test_invocation_groups.get import get_test_invocation_groups
from app.tools.entries.test_invocation_groups.search import search_test_invocation_groups
from tests.helpers import nonexistent_id
from app.tools.entries.test_invocation_groups.refresh import refresh_test_invocation_groups

pytestmark = pytest.mark.asyncio


async def _test_invocation_groups(conn, profile_id, **overrides):
    """Create full chain: session → group → run → call → test → invocation → invocation_groups."""
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    test = await create_test(conn, call_id=call.id, profiles_id=profile_id)
    call2 = await create_call(conn, run_id=run.id, session_id=session.id)
    invocation = await create_test_invocation(conn, test_id=test.id, call_id=call2.id)
    defaults = dict(test_invocation_id=invocation.id)
    defaults.update(overrides)
    return await create_test_invocation_groups(conn, **defaults)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_finds_created_test_invocation_groups(conn, profile_id):
    created = _created(await _test_invocation_groups(conn, profile_id))
    await refresh_test_invocation_groups(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    fetched = await get_test_invocation_groups(conn, ids=[lookup_id])
    row = fetched[0]
    filter_value = getattr(row, 'test_invocation_id', None)
    items = await search_test_invocation_groups(conn, test_invocation_ids=[filter_value], limit_count=20, offset_count=0)

    assert len(items) >= 1
    assert any(item["id"] == lookup_id for item in items)


async def test_returns_empty_for_unmatched_filter(conn, profile_id):
    created = _created(await _test_invocation_groups(conn, profile_id))
    await refresh_test_invocation_groups(conn)
    items = await search_test_invocation_groups(conn, test_invocation_ids=[nonexistent_id()], limit_count=20, offset_count=0)

    assert items == []


async def test_respects_limit(conn, profile_id):
    created = _created(await _test_invocation_groups(conn, profile_id))
    await refresh_test_invocation_groups(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    fetched = await get_test_invocation_groups(conn, ids=[lookup_id])
    row = fetched[0]
    filter_value = getattr(row, 'test_invocation_id', None)
    items = await search_test_invocation_groups(conn, test_invocation_ids=[filter_value], limit_count=1, offset_count=0)

    assert len(items) <= 1
