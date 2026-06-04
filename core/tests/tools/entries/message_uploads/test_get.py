"""Tests for get_message_upload."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.message_uploads.get import get_message_upload
from app.tools.entries.messages.create import create_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _deps(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id
    )
    message = await create_message(
        conn, redis_client, run_id=run.id, role="assistant"
    )
    upload = await create_upload(
        conn,
        redis_client,
        session_id=session.id,
        file_path="test/attachment.pdf",
        mime_type="application/pdf",
        size=2048,
    )
    return session, message, upload


async def test_gets_created_message_upload(conn, redis_client, profile_id):
    session, message, upload = await _deps(conn, redis_client, profile_id)
    created = await create_message_upload(
        conn,
        redis_client,
        message_id=message.id,
        upload_id=upload.id,
        session_id=session.id,
    )

    junction = await get_message_upload(conn, created.id, redis_client)

    assert junction is not None
    assert junction.id == created.id
    assert junction.message_id == message.id
    assert junction.upload_id == upload.id
    assert junction.session_id == session.id
    assert junction.active is True


async def test_get_message_upload_bypass_cache_reads_db(
    conn, redis_client, profile_id
):
    session, message, upload = await _deps(conn, redis_client, profile_id)
    created = await create_message_upload(
        conn,
        redis_client,
        message_id=message.id,
        upload_id=upload.id,
        session_id=session.id,
    )

    junction = await get_message_upload(
        conn, created.id, redis_client, bypass_cache=True
    )

    assert junction is not None
    assert junction.message_id == message.id
    assert junction.upload_id == upload.id


async def test_returns_none_for_missing_id(conn, redis_client):
    junction = await get_message_upload(conn, nonexistent_id(), redis_client)

    assert junction is None
