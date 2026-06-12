"""Tests for refresh_group_impl."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.infra.group.refresh import refresh_group_impl
pytestmark = pytest.mark.asyncio

async def test_refresh_returns_success(monkeypatch):
    pool, redis = AsyncMock(), AsyncMock()
    monkeypatch.setattr("app.infra.refresh.queue.resolve_profile_identity_context", AsyncMock(return_value=object()))
    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", AsyncMock())
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await refresh_group_impl(pool, redis, profile_id=uuid4())
    assert result.success is True
    assert "groups_mv" in result.refreshed_views

async def test_refresh_raises_401(monkeypatch):
    monkeypatch.setattr("app.infra.refresh.queue.resolve_profile_identity_context", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await refresh_group_impl(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_refresh_no_redis(monkeypatch):
    monkeypatch.setattr("app.infra.refresh.queue.resolve_profile_identity_context", AsyncMock(return_value=object()))
    pool = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await refresh_group_impl(pool, None, profile_id=uuid4())
    assert result.success is True


async def test_refresh_busts_cross_entity_home_practice_tags(monkeypatch):
    """C5: a group (simulation-backing) mutation must invalidate the global
    ``home``/``practice`` cache tags, not just ``groups``/``artifacts``. Those
    profile-scoped reads render the group/simulation title and carry no
    ``groups``/``artifacts`` tag, so a rename would otherwise leave the
    home/practice cards stale for the full 300s TTL."""
    monkeypatch.setattr(
        "app.infra.refresh.queue.resolve_profile_identity_context",
        AsyncMock(return_value=object()),
    )
    invalidated: list[str] = []

    async def mock_invalidate(tags, redis=None):
        invalidated.extend(tags)

    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", mock_invalidate)
    pool = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await refresh_group_impl(pool, AsyncMock(), profile_id=uuid4())

    assert result.success is True
    for tag in ("groups", "artifacts", "home", "practice"):
        assert tag in result.invalidated_tags
        assert tag in invalidated
