"""Tests for home_refresh — refresh_home_client."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.home_refresh import refresh_home_client

pytestmark = pytest.mark.asyncio


async def test_refresh_returns_success_response(monkeypatch):
    profile_id = uuid4()
    mock_pool = AsyncMock()
    mock_redis = AsyncMock()

    monkeypatch.setattr(
        "app.infra.home_refresh.resolve_profile_identity_context",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        "app.infra.home_refresh.refresh_home",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.utils.cache.invalidate_tags.invalidate_tags",
        AsyncMock(),
    )

    # Mock pool.acquire context manager
    conn_mock = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn_mock)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await refresh_home_client(mock_pool, mock_redis, profile_id=profile_id)
    assert result.success is True
    assert "home_mv" in result.refreshed_views
    assert "home" in result.invalidated_tags


async def test_refresh_raises_401_when_no_profile(monkeypatch):
    profile_id = uuid4()
    mock_pool = AsyncMock()
    mock_redis = AsyncMock()

    monkeypatch.setattr(
        "app.infra.home_refresh.resolve_profile_identity_context",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await refresh_home_client(mock_pool, mock_redis, profile_id=profile_id)
    assert exc_info.value.status_code == 401


async def test_refresh_skips_invalidation_when_no_redis(monkeypatch):
    profile_id = uuid4()
    mock_pool = AsyncMock()

    monkeypatch.setattr(
        "app.infra.home_refresh.resolve_profile_identity_context",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        "app.infra.home_refresh.refresh_home",
        AsyncMock(),
    )

    conn_mock = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn_mock)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await refresh_home_client(mock_pool, None, profile_id=profile_id)
    assert result.success is True
