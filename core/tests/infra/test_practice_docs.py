"""Tests for practice_docs — docs_practice_client."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.infra.practice_docs import docs_practice_client
pytestmark = pytest.mark.asyncio

async def test_docs_raises_401_when_no_profile(monkeypatch):
    monkeypatch.setattr("app.infra.practice_docs.resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc:
        await docs_practice_client(pool, redis, profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_docs_returns_response(monkeypatch):
    monkeypatch.setattr("app.infra.practice_docs.resolve_profile_identity_context", AsyncMock(return_value=AsyncMock()))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await docs_practice_client(pool, redis, profile_id=uuid4())
    assert result.name == "practice"

async def test_docs_has_page_metadata(monkeypatch):
    monkeypatch.setattr("app.infra.practice_docs.resolve_profile_identity_context", AsyncMock(return_value=AsyncMock()))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    result = await docs_practice_client(pool, redis, profile_id=uuid4())
    assert result.page_metadata is not None
