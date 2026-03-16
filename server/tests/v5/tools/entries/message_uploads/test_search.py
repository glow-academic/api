"""Tests for message_uploads search."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.groups.create import create_group
from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.message_uploads.search import search_message_uploads
from app.tools.entries.messages.create import create_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    message = await create_message(conn, run_id=run.id, role="assistant")
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/attachment.pdf",
        mime_type="application/pdf",
        size=2048,
    )
    return session, message, upload


async def test_search_finds_created(conn, profile_id):
    session, message, upload = await _deps(conn, profile_id)
    await create_message_upload(
        conn, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_message_uploads(conn, message_ids=[message.id])

    assert len(results) == 1
    assert results[0].message_id == message.id
    assert results[0].upload_id == upload.id


async def test_search_filters_by_message_id(conn, profile_id):
    session, message, upload = await _deps(conn, profile_id)
    await create_message_upload(
        conn, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_message_uploads(conn, message_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_filters_by_upload_id(conn, profile_id):
    session, message, upload = await _deps(conn, profile_id)
    await create_message_upload(
        conn, message_id=message.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_message_uploads(conn, upload_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_pagination(conn, profile_id):
    session, message, upload1 = await _deps(conn, profile_id)
    upload2 = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/attachment2.pdf",
        mime_type="application/pdf",
        size=2048,
    )
    await create_message_upload(
        conn, message_id=message.id, upload_id=upload1.id, session_id=session.id
    )
    await create_message_upload(
        conn, message_id=message.id, upload_id=upload2.id, session_id=session.id
    )

    results = await search_message_uploads(conn, message_ids=[message.id], limit=1)

    assert len(results) == 1
