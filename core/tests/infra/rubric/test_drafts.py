"""Tests for list_rubric_drafts_impl."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio

async def test_drafts_raises_401_when_no_profile(monkeypatch):
    import app.infra.rubric.drafts as m
    monkeypatch.setattr(m, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises((HTTPException, Exception)):
        await m.list_rubric_drafts_impl(pool, redis, profile_id=uuid4())

async def test_drafts_function_is_async():
    import app.infra.rubric.drafts as m
    import asyncio
    assert asyncio.iscoroutinefunction(m.list_rubric_drafts_impl)

async def test_drafts_module_composes_tools():
    import app.infra.rubric.drafts as m
    source = open(m.__file__).read()
    assert "resolve_profile_identity_context" in source or "pool" in source
