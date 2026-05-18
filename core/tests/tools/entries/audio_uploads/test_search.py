"""Tests for audio_uploads search."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.audio_uploads.create import create_audio_upload
from app.tools.entries.audio_uploads.search import search_audio_uploads
from app.tools.entries.audios.create import create_audio
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    audio = await create_audio(conn, session_id=session.id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/audio.mp3",
        mime_type="audio/mpeg",
        size=2048,
    )
    return session, audio, upload


async def test_search_finds_created(conn, profile_id):
    session, audio, upload = await _deps(conn, profile_id)
    await create_audio_upload(
        conn, audio_id=audio.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_audio_uploads(conn, audio_ids=[audio.id])

    assert len(results) == 1
    assert results[0].audio_id == audio.id
    assert results[0].upload_id == upload.id


async def test_search_filters_by_audio_id(conn, profile_id):
    session, audio, upload = await _deps(conn, profile_id)
    await create_audio_upload(
        conn, audio_id=audio.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_audio_uploads(conn, audio_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_filters_by_upload_id(conn, profile_id):
    session, audio, upload = await _deps(conn, profile_id)
    await create_audio_upload(
        conn, audio_id=audio.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_audio_uploads(conn, upload_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_pagination(conn, profile_id):
    session, audio, upload1 = await _deps(conn, profile_id)
    upload2 = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/audio2.mp3",
        mime_type="audio/mpeg",
        size=2048,
    )
    await create_audio_upload(
        conn, audio_id=audio.id, upload_id=upload1.id, session_id=session.id
    )
    await create_audio_upload(
        conn, audio_id=audio.id, upload_id=upload2.id, session_id=session.id
    )

    results = await search_audio_uploads(conn, audio_ids=[audio.id], limit=1)

    assert len(results) == 1
