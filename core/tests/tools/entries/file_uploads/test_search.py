"""Tests for file_uploads search."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.file_uploads.search import search_file_uploads
from app.tools.entries.files.create import create_file
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _deps(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    file = await create_file(conn, redis_client, session_id=session.id)
    upload = await create_upload(
        conn,
        redis_client, session_id=session.id,
        file_path="test/doc.pdf",
        mime_type="application/pdf",
        size=3072,
    )
    return session, file, upload


async def test_search_finds_created(conn, redis_client, profile_id):
    session, file, upload = await _deps(conn, redis_client, profile_id)
    await create_file_upload(
        conn, redis_client, file_id=file.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_file_uploads(conn, redis_client, file_ids=[file.id])

    assert len(results) == 1
    assert results[0].file_id == file.id
    assert results[0].upload_id == upload.id


async def test_search_filters_by_file_id(conn, redis_client, profile_id):
    session, file, upload = await _deps(conn, redis_client, profile_id)
    await create_file_upload(
        conn, redis_client, file_id=file.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_file_uploads(conn, redis_client, file_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_filters_by_upload_id(conn, redis_client, profile_id):
    session, file, upload = await _deps(conn, redis_client, profile_id)
    await create_file_upload(
        conn, redis_client, file_id=file.id, upload_id=upload.id, session_id=session.id
    )

    results = await search_file_uploads(conn, redis_client, upload_ids=[nonexistent_id()])

    assert len(results) == 0


async def test_search_pagination(conn, redis_client, profile_id):
    session, file, upload1 = await _deps(conn, redis_client, profile_id)
    upload2 = await create_upload(
        conn,
        redis_client, session_id=session.id,
        file_path="test/doc2.pdf",
        mime_type="application/pdf",
        size=3072,
    )
    await create_file_upload(
        conn, redis_client, file_id=file.id, upload_id=upload1.id, session_id=session.id
    )
    await create_file_upload(
        conn, redis_client, file_id=file.id, upload_id=upload2.id, session_id=session.id
    )

    results = await search_file_uploads(conn, redis_client, file_ids=[file.id], limit=1)

    assert len(results) == 1
