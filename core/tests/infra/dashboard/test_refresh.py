"""Tests for refresh_dashboard_impl."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.infra.dashboard.refresh import refresh_dashboard_impl
pytestmark = pytest.mark.asyncio

async def test_refresh_returns_success(monkeypatch):
    monkeypatch.setattr("app.infra.dashboard.refresh.resolve_profile_identity_context", AsyncMock(return_value=object()))
    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", AsyncMock())
    result = await refresh_dashboard_impl(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert result.success is True
    assert result.refreshed_views == []
    assert "dashboard" in result.invalidated_tags

async def test_refresh_raises_401(monkeypatch):
    monkeypatch.setattr("app.infra.dashboard.refresh.resolve_profile_identity_context", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await refresh_dashboard_impl(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_refresh_no_redis(monkeypatch):
    monkeypatch.setattr("app.infra.dashboard.refresh.resolve_profile_identity_context", AsyncMock(return_value=object()))
    result = await refresh_dashboard_impl(AsyncMock(), None, profile_id=uuid4())
    assert result.success is True
