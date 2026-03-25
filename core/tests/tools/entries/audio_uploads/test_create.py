"""Tests for create_audio_upload."""

import pytest

from app.tools.entries.audio_uploads.create import create_audio_upload
from app.tools.entries.audio_uploads.get import get_audio_upload
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


async def test_creates_audio_upload_entry(conn, profile_id):
    session, audio, upload = await _deps(conn, profile_id)
    result = await create_audio_upload(
        conn, audio_id=audio.id, upload_id=upload.id, session_id=session.id
    )

    assert result.id is not None


async def test_audio_upload_exists_in_table(conn, profile_id):
    session, audio, upload = await _deps(conn, profile_id)
    result = await create_audio_upload(
        conn, audio_id=audio.id, upload_id=upload.id, session_id=session.id
    )

    row = await get_audio_upload(conn, result.id)

    assert row is not None
    assert row.audio_id == audio.id
    assert row.upload_id == upload.id
    assert row.session_id == session.id
    assert row.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session, audio, upload = await _deps(conn, profile_id)
    result = await create_audio_upload(
        conn, audio_id=audio.id, upload_id=upload.id, session_id=session.id, mcp=True
    )

    row = await get_audio_upload(conn, result.id)

    assert row is not None
    assert row.mcp is True
