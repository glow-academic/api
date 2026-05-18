"""Tests for create_file."""

import pytest

from app.tools.entries.files.create import create_file
from app.tools.entries.files.get import get_file
from app.tools.entries.sessions.create import create_session
from app.tools.resources.files.create import (
    create_file as create_file_resource,
)

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_creates_file_entry(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_file(conn, session_id=session.id)

    assert result.id is not None


async def test_file_exists_in_table(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_file(conn, session_id=session.id)

    file = await get_file(conn, result.id)

    assert file is not None
    assert file.session_id == session.id
    assert file.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_file(conn, session_id=session.id, mcp=True)

    file = await get_file(conn, result.id)

    assert file is not None
    assert file.mcp is True


async def test_links_files_resource(conn, profile_id, redis_client):
    session = await _session(conn, profile_id)
    resource = await create_file_resource(conn, redis=redis_client)
    result = await create_file(conn, session_id=session.id, files_id=resource.id)

    assert result.id is not None
