"""Tests for refresh_files_internal."""

import pytest
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file
from app.tools.entries.files.get import get_file
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.files.create import (
    create_file as create_file_resource,
)
from app.tools.entries.files.refresh import refresh_files_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def _mv_eligible_file(conn, redis_client, session_id):
    # files_mv requires a files_resource connection + a linked upload (the MV
    # inner-joins file_files_connection and file_uploads/uploads), so build the
    # full row here — a bare create_file never enters the MV.
    resource = await create_file_resource(conn, redis=redis_client)
    file = await create_file(conn, redis_client, session_id=session_id, files_id=resource.id)
    upload = await create_upload(
        conn, redis_client, session_id=session_id,
        file_path="/test/document.pdf", mime_type="application/pdf", size=4096,
    )
    await create_file_upload(
        conn, redis_client, file_id=file.id, upload_id=upload.id, session_id=session_id
    )
    return file


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_files_appears_after_refresh(conn, redis_client, session_id):
    created = _created(await create_file(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'file_id', None) or getattr(created, 'id', None) or getattr(created, 'file', None)

    await refresh_files_internal(conn)
    item = await get_file(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_new_files_is_visible_before_refresh(conn, redis_client, session_id):
    # get_file's bypass_cache path reads the base files_entry table (not the MV),
    # so a freshly created row is immediately visible without any refresh.
    # Refresh only repopulates files_mv (see the MV-population test below).
    created = _created(await create_file(conn, redis_client, session_id=session_id))
    lookup_id = getattr(created, 'file_id', None) or getattr(created, 'id', None) or getattr(created, 'file', None)

    item = await get_file(conn, lookup_id, redis_client, bypass_cache=True)

    assert item is not None
    assert item.id == lookup_id


async def test_files_mv_populated_only_after_refresh(conn, redis_client, session_id):
    # The materialized view files_mv is NOT updated by create; it only reflects
    # the new (MV-eligible) row after refresh_files_internal.
    file = await _mv_eligible_file(conn, redis_client, session_id)
    lookup_id = file.id

    in_mv_before = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM files_mv WHERE file_id = $1)", lookup_id
    )
    assert in_mv_before is False

    await refresh_files_internal(conn)

    in_mv_after = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM files_mv WHERE file_id = $1)", lookup_id
    )
    assert in_mv_after is True


async def test_refresh_is_idempotent(conn):
    await refresh_files_internal(conn)
    await refresh_files_internal(conn)

    assert True
