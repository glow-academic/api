"""Tests for websocket tool registry."""

import asyncio

import pytest

from app.infra.websocket.tool_registry import resolve_tool_result, wait_for_tool_result

pytestmark = pytest.mark.asyncio


async def test_wait_for_tool_result_returns_pre_resolved_result():
    resolve_tool_result("call-1", {"ok": True})

    result = await wait_for_tool_result("call-1", timeout_seconds=0.1)

    assert result == {"ok": True}


async def test_wait_for_tool_result_resolves_future_when_result_arrives_later():
    async def _resolve_later() -> None:
        await asyncio.sleep(0)
        resolve_tool_result("call-2", {"value": 42})

    task = asyncio.create_task(_resolve_later())
    result = await wait_for_tool_result("call-2", timeout_seconds=0.2)
    await task

    assert result == {"value": 42}


async def test_wait_for_tool_result_returns_none_on_timeout():
    result = await wait_for_tool_result("call-timeout", timeout_seconds=0.01)

    assert result is None
