"""Tests for call_uploads search."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.call_uploads.create import create_call_upload
from app.tools.entries.call_uploads.search import search_call_uploads
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/response.json",
        mime_type="application/json",
        size=512,
    )
    return session, call, upload


async def test_search_finds_created(conn, profile_id):
    session, call, upload = await _deps(conn, profile_id)
    await create_call_upload(
        conn, call_id=call.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_call_uploads(conn, call_ids=[call.id])

    assert len(results) == 1
    assert results[0].call_id == call.id
    assert results[0].upload_id == upload.id


async def test_search_filters_by_call_id(conn, profile_id):
    session, call, upload = await _deps(conn, profile_id)
    await create_call_upload(
        conn, call_id=call.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_call_uploads(conn, call_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_filters_by_upload_id(conn, profile_id):
    session, call, upload = await _deps(conn, profile_id)
    await create_call_upload(
        conn, call_id=call.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_call_uploads(conn, upload_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_pagination(conn, profile_id):
    session, call, upload1 = await _deps(conn, profile_id)
    upload2 = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/response2.json",
        mime_type="application/json",
        size=512,
    )
    await create_call_upload(
        conn, call_id=call.id, upload_id=upload1.id, session_id=session.id
    )
    await create_call_upload(
        conn, call_id=call.id, upload_id=upload2.id, session_id=session.id
    )

    results = await search_call_uploads(conn, call_ids=[call.id], limit=1)

    assert len(results) == 1
