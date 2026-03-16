"""Tests for create_image."""

import pytest

from app.tools.entries.images.create import create_image
from app.tools.entries.images.get import get_image
from app.tools.entries.sessions.create import create_session
from app.tools.resources.images.create import (
    create_image as create_image_resource,
)

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_creates_image_entry(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_image(conn, session_id=session.id)

    assert result.id is not None


async def test_image_exists_in_table(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_image(conn, session_id=session.id)

    image = await get_image(conn, result.id)

    assert image is not None
    assert image.session_id == session.id
    assert image.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_image(conn, session_id=session.id, mcp=True)

    image = await get_image(conn, result.id)

    assert image is not None
    assert image.mcp is True


async def test_links_images_resource(conn, profile_id, redis_client):
    session = await _session(conn, profile_id)
    resource = await create_image_resource(
        conn, name="test", description="test", redis=redis_client
    )
    result = await create_image(conn, session_id=session.id, images_id=resource.id)

    assert result.id is not None
