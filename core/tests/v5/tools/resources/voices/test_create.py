"""Tests for create_voice."""

import pytest

from app.tools.resources.voices.create import create_voice
from app.tools.resources.voices.get import get_voices

pytestmark = pytest.mark.asyncio


async def test_creates_new_voice(conn, redis_client):
    result = await create_voice(conn, "test-voice", redis_client)

    assert result.voice == "test-voice"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_voice(conn, "test-voice-visible", redis_client)

    items = await get_voices(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].voice == "test-voice-visible"


async def test_creates_second_row(conn, redis_client):
    first = await create_voice(conn, "duplicate-voice", redis_client)
    second = await create_voice(conn, "duplicate-voice", redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_voice(conn, "mcp-voice", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
