"""Tests for get_upload."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.uploads.get import get_upload
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def test_gets_created_upload(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    created = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/get-me.pdf",
        mime_type="application/pdf",
        size=4096,
    )

    upload = await get_upload(conn, created.id, redis_client)

    assert upload is not None
    assert upload.id == created.id
    assert upload.session_id == session.id
    assert upload.file_path == "test/get-me.pdf"
    assert upload.mime_type == "application/pdf"
    assert upload.size == 4096
    assert upload.active is True


async def test_get_upload_bypass_cache_reads_db(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    created = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/bypass.txt",
        mime_type="text/plain",
        size=128,
    )

    upload = await get_upload(conn, created.id, redis_client, bypass_cache=True)

    assert upload is not None
    assert upload.id == created.id
    assert upload.file_path == "test/bypass.txt"
    assert upload.size == 128


async def test_returns_none_for_missing_id(conn, redis_client):
    upload = await get_upload(conn, nonexistent_id(), redis_client)

    assert upload is None
