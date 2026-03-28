"""Tests for get_audio."""

import pytest
from app.tools.entries.audios.create import create_audio
from app.tools.entries.audios.get import get_audio
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_audios(conn, session_id):
    created = _created(await create_audio(conn, session_id=session_id))
    lookup_id = getattr(created, 'audio_id', None) or getattr(created, 'id', None) or getattr(created, 'audio', None)
    item = await get_audio(conn, lookup_id)

    assert item is not None
    assert item.id == lookup_id


async def test_returns_empty_for_missing_id(conn):
    item = await get_audio(conn, nonexistent_id())

    assert item is None


async def test_returns_created_item_after_second_lookup(conn, session_id):
    created = _created(await create_audio(conn, session_id=session_id))
    lookup_id = getattr(created, 'audio_id', None) or getattr(created, 'id', None) or getattr(created, 'audio', None)
    first = await get_audio(conn, lookup_id)
    second = await get_audio(conn, lookup_id)

    assert first is not None
    assert second is not None
    assert second.id == lookup_id
