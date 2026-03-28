"""Tests for refresh_activity_impl."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.infra.activity.refresh import refresh_activity_impl
pytestmark = pytest.mark.asyncio

async def test_refresh_returns_success(monkeypatch):
    mock_pool, mock_redis = AsyncMock(), AsyncMock()
    monkeypatch.setattr("app.infra.activity.refresh.resolve_profile_identity_context", AsyncMock(return_value=object()))
    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", AsyncMock())
    conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await refresh_activity_impl(mock_pool, mock_redis, profile_id=uuid4())
    assert result.success is True
    assert "activity_mv" in result.refreshed_views

async def test_refresh_raises_401(monkeypatch):
    monkeypatch.setattr("app.infra.activity.refresh.resolve_profile_identity_context", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await refresh_activity_impl(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_refresh_skips_cache_without_redis(monkeypatch):
    monkeypatch.setattr("app.infra.activity.refresh.resolve_profile_identity_context", AsyncMock(return_value=object()))
    pool = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await refresh_activity_impl(pool, None, profile_id=uuid4())
    assert result.success is True
