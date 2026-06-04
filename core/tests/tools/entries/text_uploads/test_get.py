"""Tests for get_text_upload."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.text_uploads.get import get_text_upload
from app.tools.entries.texts.create import create_text
from app.tools.entries.uploads.create import create_upload
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _deps(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    text = await create_text(conn, redis_client, session_id=session.id)
    upload = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/linked.txt",
        mime_type="text/plain",
        size=512,
    )
    return session, text, upload


async def test_gets_created_text_upload(conn, redis_client, profile_id):
    session, text, upload = await _deps(conn, redis_client, profile_id)
    created = await create_text_upload(
        conn,
        redis_client,
        text_id=text.id,
        upload_id=upload.id,
        session_id=session.id,
    )

    junction = await get_text_upload(conn, created.id, redis_client)

    assert junction is not None
    assert junction.id == created.id
    assert junction.text_id == text.id
    assert junction.upload_id == upload.id
    assert junction.session_id == session.id
    assert junction.active is True


async def test_get_text_upload_bypass_cache_reads_db(conn, redis_client, profile_id):
    session, text, upload = await _deps(conn, redis_client, profile_id)
    created = await create_text_upload(
        conn,
        redis_client,
        text_id=text.id,
        upload_id=upload.id,
        session_id=session.id,
    )

    junction = await get_text_upload(conn, created.id, redis_client, bypass_cache=True)

    assert junction is not None
    assert junction.text_id == text.id
    assert junction.upload_id == upload.id


async def test_returns_none_for_missing_id(conn, redis_client):
    junction = await get_text_upload(conn, nonexistent_id(), redis_client)

    assert junction is None
