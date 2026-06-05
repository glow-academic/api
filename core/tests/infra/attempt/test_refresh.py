"""Tests for refresh_attempt_impl."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.infra.attempt.refresh import refresh_attempt_impl
pytestmark = pytest.mark.asyncio

async def test_refresh_returns_success(monkeypatch):
    pool, redis = AsyncMock(), AsyncMock()
    monkeypatch.setattr("app.infra.refresh.queue.resolve_profile_identity_context", AsyncMock(return_value=object()))
    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", AsyncMock())
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await refresh_attempt_impl(pool, redis, profile_id=uuid4())
    assert result.success is True
    assert "attempt_mv" in result.refreshed_views

async def test_refresh_raises_401(monkeypatch):
    monkeypatch.setattr("app.infra.refresh.queue.resolve_profile_identity_context", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await refresh_attempt_impl(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_refresh_no_redis(monkeypatch):
    monkeypatch.setattr("app.infra.refresh.queue.resolve_profile_identity_context", AsyncMock(return_value=object()))
    pool = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await refresh_attempt_impl(pool, None, profile_id=uuid4())
    assert result.success is True


async def test_refresh_honors_caller_targets(monkeypatch):
    """Caller-supplied ``targets`` must be enqueued, not swallowed.

    Regression guard: the attempt-cluster mutates (message/grade/feedback/
    hint/strength/improvement/analysis/response/chat_*) pass the specific
    ``*_mv`` they invalidated. Previously ``targets`` was eaten by ``**_kwargs``
    and only ALL_TARGETS was ever enqueued, so per-feature MVs like
    ``attempt_message_tree_mv`` never had a refresh enqueued and reads went
    permanently stale until a manual full refresh. ``refreshed_views`` echoes
    the targets actually forwarded to the enqueue helper.

    Fail-pre (targets ignored): attempt_message_tree_mv absent + ALL_TARGETS
    leaks through. Pass-post (targets honored): only the requested target.
    """
    from app.infra.attempt.refresh import ALL_TARGETS

    pool, redis = AsyncMock(), AsyncMock()
    monkeypatch.setattr(
        "app.infra.refresh.queue.resolve_profile_identity_context",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", AsyncMock())
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await refresh_attempt_impl(
        pool, redis, profile_id=uuid4(),
        targets=["attempt_message_tree_mv", "attempt_message_mv"],
    )

    assert result.success is True
    assert "attempt_message_tree_mv" in result.refreshed_views
    assert "attempt_message_mv" in result.refreshed_views
    # The caller asked for a specific pair — the generic ALL_TARGETS set must
    # not leak in when explicit targets are supplied.
    assert set(result.refreshed_views) == {"attempt_message_tree_mv", "attempt_message_mv"}
    assert set(result.refreshed_views) != set(ALL_TARGETS)


async def test_refresh_defaults_to_all_targets_when_unspecified(monkeypatch):
    """No targets → fall back to ALL_TARGETS (unchanged default behavior)."""
    from app.infra.attempt.refresh import ALL_TARGETS

    pool, redis = AsyncMock(), AsyncMock()
    monkeypatch.setattr(
        "app.infra.refresh.queue.resolve_profile_identity_context",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", AsyncMock())
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await refresh_attempt_impl(pool, redis, profile_id=uuid4())
    assert set(result.refreshed_views) == set(ALL_TARGETS)
