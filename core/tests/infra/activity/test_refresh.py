"""Tests for refresh_activity_impl."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.activity.refresh import ALL_TARGETS, refresh_activity_impl
from app.infra.refresh.types import RefreshResponse

pytestmark = pytest.mark.asyncio


async def test_refresh_returns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_pool, mock_redis = AsyncMock(), AsyncMock()
    profile_id = uuid4()
    response = RefreshResponse(
        success=True,
        refreshed_views=ALL_TARGETS,
        invalidated_tags=["activity", "artifacts"],
    )
    enqueue = AsyncMock(return_value=response)
    monkeypatch.setattr("app.infra.activity.refresh.enqueue_refreshes", enqueue)

    result = await refresh_activity_impl(mock_pool, mock_redis, profile_id=profile_id)

    assert result.success is True
    assert result.refreshed_views == ALL_TARGETS
    enqueue.assert_awaited_once_with(
        mock_pool,
        mock_redis,
        profile_id=profile_id,
        session_id=None,
        artifact_type="activity",
        targets=ALL_TARGETS,
        idempotency_key=None,
        tags=["activity", "artifacts"],
        soft=False,
        accept=None,
    )


async def test_refresh_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    enqueue = AsyncMock(
        side_effect=HTTPException(status_code=401, detail="Profile not found")
    )
    monkeypatch.setattr("app.infra.activity.refresh.enqueue_refreshes", enqueue)

    with pytest.raises(HTTPException) as exc:
        await refresh_activity_impl(AsyncMock(), AsyncMock(), profile_id=uuid4())

    assert exc.value.status_code == 401


async def test_refresh_skips_cache_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = RefreshResponse(
        success=True,
        refreshed_views=ALL_TARGETS,
        invalidated_tags=["activity", "artifacts"],
    )
    monkeypatch.setattr(
        "app.infra.activity.refresh.enqueue_refreshes",
        AsyncMock(return_value=response),
    )

    result = await refresh_activity_impl(AsyncMock(), None, profile_id=uuid4())

    assert result.success is True
    assert result.refreshed_views == ALL_TARGETS
