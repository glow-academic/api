"""Tests for text_uploads search."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.sessions.create import create_session
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.text_uploads.search import search_text_uploads
from app.tools.entries.texts.create import create_text
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    text = await create_text(conn, session_id=session.id)
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )
    return session, text, upload


async def test_search_finds_created(conn, profile_id):
    session, text, upload = await _deps(conn, profile_id)
    await create_text_upload(
        conn, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_text_uploads(conn, text_ids=[text.id])

    assert len(results) == 1
    assert results[0].text_id == text.id
    assert results[0].upload_id == upload.id


async def test_search_filters_by_text_id(conn, profile_id):
    session, text, upload = await _deps(conn, profile_id)
    await create_text_upload(
        conn, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_text_uploads(conn, text_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_filters_by_upload_id(conn, profile_id):
    session, text, upload = await _deps(conn, profile_id)
    await create_text_upload(
        conn, text_id=text.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_text_uploads(conn, upload_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_pagination(conn, profile_id):
    session, text, upload1 = await _deps(conn, profile_id)
    upload2 = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/file2.txt",
        mime_type="text/plain",
        size=1024,
    )
    await create_text_upload(
        conn, text_id=text.id, upload_id=upload1.id, session_id=session.id
    )
    await create_text_upload(
        conn, text_id=text.id, upload_id=upload2.id, session_id=session.id
    )

    results = await search_text_uploads(conn, text_ids=[text.id], limit=1)

    assert len(results) == 1
