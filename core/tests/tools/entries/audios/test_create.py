"""Tests for create_audio."""

import pytest

from app.tools.entries.audios.create import create_audio
from app.tools.entries.audios.get import get_audio
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def test_creates_audio_entry(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_audio(conn, redis_client, session_id=session.id)

    assert result.id is not None


async def test_audio_exists_in_table(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_audio(conn, redis_client, session_id=session.id)

    audio = await get_audio(conn, result.id, redis_client)

    assert audio is not None
    assert audio.session_id == session.id
    assert audio.active is True


async def test_passes_length_seconds(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_audio(conn, redis_client, session_id=session.id, length_seconds=120)

    audio = await get_audio(conn, result.id, redis_client)

    assert audio is not None
    assert audio.length_seconds == 120


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_audio(conn, redis_client, session_id=session.id, mcp=True)

    audio = await get_audio(conn, result.id, redis_client)

    assert audio is not None
    assert audio.mcp is True
