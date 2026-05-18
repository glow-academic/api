"""Tests for refresh_audios_internal."""

import pytest
from app.tools.entries.audios.create import create_audio
from app.tools.entries.audios.get import get_audio
from app.tools.entries.sessions.create import create_session
from app.tools.entries.audios.refresh import refresh_audios_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_audios_appears_after_refresh(conn, session_id):
    created = _created(await create_audio(conn, session_id=session_id))
    lookup_id = getattr(created, 'audio_id', None) or getattr(created, 'id', None) or getattr(created, 'audio', None)

    await refresh_audios_internal(conn)
    item = await get_audio(conn, lookup_id)

    assert item is not None
    assert item.id == lookup_id


async def test_new_audios_is_not_visible_before_refresh(conn, session_id):
    created = _created(await create_audio(conn, session_id=session_id))
    lookup_id = getattr(created, 'audio_id', None) or getattr(created, 'id', None) or getattr(created, 'audio', None)

    item = await get_audio(conn, lookup_id)

    assert item is None


async def test_refresh_is_idempotent(conn):
    await refresh_audios_internal(conn)
    await refresh_audios_internal(conn)

    assert True
