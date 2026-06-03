"""Tests for search_files."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file
from app.tools.entries.files.search import search_files
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.files.create import (
    create_file as create_file_resource,
)

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    resource = await create_file_resource(conn, redis=redis_client)
    file = await create_file(conn, redis_client, session_id=session.id, files_id=resource.id)
    upload = await create_upload(
        conn,
        redis_client, session_id=session.id,
        file_path="/test/document.pdf",
        mime_type="application/pdf",
        size=4096,
    )
    await create_file_upload(
        conn, redis_client, file_id=file.id, upload_id=upload.id, session_id=session.id
    )
    return file, resource.id


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)

    items = await search_files(conn, redis_client, bypass_mv=True)

    assert len(items) >= 1


async def test_filters_by_files_ids(conn, redis_client, profile_id):
    _, files_id = await _setup(conn, redis_client, profile_id)

    items = await search_files(conn, redis_client, files_ids=[files_id], bypass_mv=True)

    assert len(items) >= 1
    assert all(item.files_id == files_id for item in items)


async def test_filters_by_mime_type(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)

    items = await search_files(conn, redis_client, mime_type="application/pdf", bypass_mv=True)

    assert len(items) >= 1
    assert all(item.mime_type == "application/pdf" for item in items)


async def test_filters_by_nonexistent_files_ids(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)

    items = await search_files(conn, redis_client, files_ids=[nonexistent_id()], bypass_mv=True)

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)

    items = await search_files(conn, redis_client, limit=1, bypass_mv=True)

    assert len(items) <= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    file, files_id = await _setup(conn, redis_client, profile_id)

    items = await search_files(conn, redis_client, files_ids=[files_id], bypass_mv=True)

    file_ids = [item.file_id for item in items]
    assert file.id in file_ids
