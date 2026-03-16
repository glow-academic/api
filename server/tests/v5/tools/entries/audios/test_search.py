"""Tests for search_audios."""

import pytest

from app.tools.entries.audio_uploads.create import create_audio_upload
from app.tools.entries.audios.create import create_audio
from app.tools.entries.audios.search import search_audios
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    audio = await create_audio(conn, session_id=session.id, length_seconds=30)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="/test/audio.mp3",
        mime_type="audio/mpeg",
        size=1024,
    )
    await create_audio_upload(
        conn, audio_id=audio.id, upload_id=upload.id, session_id=session.id
    )
    return audio


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)

    items = await search_audios(conn, bypass_mv=True)

    assert len(items) >= 1


async def test_pagination_limit(conn, profile_id):
    await _setup(conn, profile_id)

    items = await search_audios(conn, limit=1, bypass_mv=True)

    assert len(items) <= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    audio = await _setup(conn, profile_id)

    items = await search_audios(conn, bypass_mv=True)

    audio_ids = [item.audio_id for item in items]
    assert audio.id in audio_ids
