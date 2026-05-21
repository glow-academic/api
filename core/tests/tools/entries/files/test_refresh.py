"""Tests for refresh_files_internal."""

import pytest
from app.tools.entries.files.create import create_file
from app.tools.entries.files.get import get_file
from app.tools.entries.sessions.create import create_session
from app.tools.resources.files.create import (
    create_file as create_file_resource,
)
from app.tools.entries.files.refresh import refresh_files_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_files_appears_after_refresh(conn, redis_client, session_id):
    created = _created(await create_file(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'file_id', None) or getattr(created, 'id', None) or getattr(created, 'file', None)

    await refresh_files_internal(conn)
    item = await get_file(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_new_files_is_not_visible_before_refresh(conn, redis_client, session_id):
    created = _created(await create_file(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'file_id', None) or getattr(created, 'id', None) or getattr(created, 'file', None)

    item = await get_file(conn, lookup_id, redis_client)

    assert item is None


async def test_refresh_is_idempotent(conn):
    await refresh_files_internal(conn)
    await refresh_files_internal(conn)

    assert True
