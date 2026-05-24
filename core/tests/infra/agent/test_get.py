"""Tests for agent get — profile check, 401 handling."""

from uuid import uuid4
import pytest
from app.infra.agent.get import get_agent_impl

pytestmark = pytest.mark.asyncio


async def test_get_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(*a, **kw):
        return None
    monkeypatch.setattr("app.infra.agent.get.resolve_common_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_agent_impl(None, None, profile_id=uuid4(), agent_id=uuid4())
    assert exc_info.value.status_code == 401


async def test_get_function_is_async_callable():
    import asyncio
    assert asyncio.iscoroutinefunction(get_agent_impl)


async def test_get_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(*a, **kw):
        return None
    monkeypatch.setattr("app.infra.agent.get.resolve_common_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_agent_impl(None, None, profile_id=uuid4(), agent_id=uuid4())
    assert "sign in" in exc_info.value.detail.lower()
