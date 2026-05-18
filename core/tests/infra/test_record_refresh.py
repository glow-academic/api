"""Tests for record_refresh — refresh_record_client."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.record_refresh import refresh_record_client

pytestmark = pytest.mark.asyncio


async def test_refresh_returns_success_with_empty_views(monkeypatch):
    monkeypatch.setattr(
        "app.infra.record_refresh.resolve_profile_identity_context",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        "app.utils.cache.invalidate_tags.invalidate_tags",
        AsyncMock(),
    )

    result = await refresh_record_client(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert result.success is True
    assert result.refreshed_views == []
    assert "record" in result.invalidated_tags


async def test_refresh_raises_401_when_no_profile(monkeypatch):
    monkeypatch.setattr(
        "app.infra.record_refresh.resolve_profile_identity_context",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await refresh_record_client(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert exc_info.value.status_code == 401


async def test_refresh_skips_invalidation_when_no_redis(monkeypatch):
    monkeypatch.setattr(
        "app.infra.record_refresh.resolve_profile_identity_context",
        AsyncMock(return_value=object()),
    )

    result = await refresh_record_client(AsyncMock(), None, profile_id=uuid4())
    assert result.success is True
    assert result.refreshed_views == []
