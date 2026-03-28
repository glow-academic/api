"""Tests for docs_chat_impl — docs orchestration."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio

async def test_docs_raises_401_when_no_profile(monkeypatch):
    import app.infra.chat.docs as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc:
        await mod.docs_chat_impl(pool, redis, profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_docs_returns_composed_response(monkeypatch):
    import app.infra.chat.docs as mod
    profile_mock = AsyncMock()
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=profile_mock))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await mod.docs_chat_impl(pool, redis, profile_id=uuid4())
    assert result.name == "chat"
    assert result.api_operations is not None

async def test_docs_has_page_metadata(monkeypatch):
    import app.infra.chat.docs as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=AsyncMock()))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await mod.docs_chat_impl(pool, redis, profile_id=uuid4())
    assert result.page_metadata is not None
