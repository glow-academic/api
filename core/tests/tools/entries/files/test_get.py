"""Tests for get_file."""

import pytest
from app.tools.entries.files.create import create_file
from app.tools.entries.files.get import get_file
from app.tools.entries.sessions.create import create_session
from app.tools.resources.files.create import (
    create_file as create_file_resource,
)
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_files(conn, session_id):
    created = _created(await create_file(conn, session_id=session_id))
    lookup_id = getattr(created, 'file_id', None) or getattr(created, 'id', None) or getattr(created, 'file', None)
    item = await get_file(conn, lookup_id)

    assert item is not None
    assert item.id == lookup_id


async def test_returns_empty_for_missing_id(conn):
    item = await get_file(conn, nonexistent_id())

    assert item is None


async def test_returns_created_item_after_second_lookup(conn, session_id):
    created = _created(await create_file(conn, session_id=session_id))
    lookup_id = getattr(created, 'file_id', None) or getattr(created, 'id', None) or getattr(created, 'file', None)
    first = await get_file(conn, lookup_id)
    second = await get_file(conn, lookup_id)

    assert first is not None
    assert second is not None
    assert second.id == lookup_id
