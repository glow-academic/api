"""Tests for practice_refresh — refresh_practice_client."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.practice_refresh import refresh_practice_client

pytestmark = pytest.mark.asyncio


async def test_refresh_returns_success_with_views_and_tags(monkeypatch):
    profile_id = uuid4()
    mock_pool = AsyncMock()
    mock_redis = AsyncMock()

    monkeypatch.setattr(
        "app.infra.practice_refresh.resolve_profile_identity_context",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        "app.infra.practice_refresh.refresh_practice",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.utils.cache.invalidate_tags.invalidate_tags",
        AsyncMock(),
    )

    conn_mock = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn_mock)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await refresh_practice_client(mock_pool, mock_redis, profile_id=profile_id)
    assert result.success is True
    assert "practice_mv" in result.refreshed_views
    assert "practice" in result.invalidated_tags


async def test_refresh_raises_401_when_no_profile(monkeypatch):
    monkeypatch.setattr(
        "app.infra.practice_refresh.resolve_profile_identity_context",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await refresh_practice_client(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert exc_info.value.status_code == 401


async def test_refresh_skips_cache_invalidation_when_no_redis(monkeypatch):
    monkeypatch.setattr(
        "app.infra.practice_refresh.resolve_profile_identity_context",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        "app.infra.practice_refresh.refresh_practice",
        AsyncMock(),
    )

    mock_pool = AsyncMock()
    conn_mock = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn_mock)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await refresh_practice_client(mock_pool, None, profile_id=uuid4())
    assert result.success is True
