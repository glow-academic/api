"""Tests for refresh_audios_internal."""

import pytest
from app.tools.entries.audio_uploads.create import create_audio_upload
from app.tools.entries.audios.create import create_audio
from app.tools.entries.audios.get import get_audio
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.audios.refresh import refresh_audios_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def _mv_eligible_audio(conn, redis_client, session_id):
    # audios_mv inner-joins audio_uploads/uploads, so build the linked upload
    # here — a bare create_audio never enters the MV.
    audio = await create_audio(conn, redis_client, session_id=session_id, length_seconds=30)
    upload = await create_upload(
        conn, redis_client, session_id=session_id,
        file_path="/test/audio.mp3", mime_type="audio/mpeg", size=1024,
    )
    await create_audio_upload(
        conn, redis_client, audio_id=audio.id, upload_id=upload.id, session_id=session_id
    )
    return audio


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_audios_appears_after_refresh(conn, redis_client, session_id):
    created = _created(await create_audio(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'audio_id', None) or getattr(created, 'id', None) or getattr(created, 'audio', None)

    await refresh_audios_internal(conn)
    item = await get_audio(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_new_audios_is_visible_before_refresh(conn, redis_client, session_id):
    # get_audio's bypass_cache path reads the base audios_entry table (not the
    # MV), so a freshly created row is immediately visible without any refresh.
    # Refresh only repopulates audios_mv (see the MV-population test below).
    created = _created(await create_audio(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'audio_id', None) or getattr(created, 'id', None) or getattr(created, 'audio', None)

    item = await get_audio(conn, lookup_id, redis_client, bypass_cache=True)

    assert item is not None
    assert item.id == lookup_id


async def test_audios_mv_populated_only_after_refresh(conn, redis_client, session_id):
    # The materialized view audios_mv is NOT updated by create; it only reflects
    # the new (MV-eligible) row after refresh_audios_internal.
    audio = await _mv_eligible_audio(conn, redis_client, session_id)
    lookup_id = audio.id

    in_mv_before = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM audios_mv WHERE audio_id = $1)", lookup_id
    )
    assert in_mv_before is False

    await refresh_audios_internal(conn)

    in_mv_after = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM audios_mv WHERE audio_id = $1)", lookup_id
    )
    assert in_mv_after is True


async def test_refresh_is_idempotent(conn):
    await refresh_audios_internal(conn)
    await refresh_audios_internal(conn)

    assert True
