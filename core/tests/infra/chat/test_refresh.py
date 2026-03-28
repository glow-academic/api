"""Tests for refresh_chat_impl."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.infra.chat.refresh import refresh_chat_impl
pytestmark = pytest.mark.asyncio

async def test_refresh_returns_success(monkeypatch):
    pool, redis = AsyncMock(), AsyncMock()
    monkeypatch.setattr("app.infra.chat.refresh.resolve_profile_identity_context", AsyncMock(return_value=object()))
    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", AsyncMock())
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await refresh_chat_impl(pool, redis, profile_id=uuid4())
    assert result.success is True
    assert "chat_mv" in result.refreshed_views
    assert "chat" in result.invalidated_tags

async def test_refresh_raises_401(monkeypatch):
    monkeypatch.setattr("app.infra.chat.refresh.resolve_profile_identity_context", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await refresh_chat_impl(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_refresh_no_redis(monkeypatch):
    monkeypatch.setattr("app.infra.chat.refresh.resolve_profile_identity_context", AsyncMock(return_value=object()))
    pool = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await refresh_chat_impl(pool, None, profile_id=uuid4())
    assert result.success is True
