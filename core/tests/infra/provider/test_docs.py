"""Tests for provider docs — profile check, response structure."""

from uuid import uuid4
import pytest
from app.infra.provider.docs import docs_provider_impl

pytestmark = pytest.mark.asyncio


async def test_docs_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.provider.docs.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await docs_provider_impl(None, None, profile_id=uuid4())
    assert exc_info.value.status_code == 401


async def test_docs_is_async_callable():
    import asyncio
    assert asyncio.iscoroutinefunction(docs_provider_impl)


async def test_docs_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.provider.docs.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await docs_provider_impl(None, None, profile_id=uuid4())
    assert "sign in" in exc_info.value.detail.lower()
