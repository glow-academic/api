"""Tests for record_export."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio

async def test_export_raises_401_when_no_profile(monkeypatch):
    import app.infra.record_export as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc:
        await mod.export_record_client(pool, redis, profile_id=uuid4(), target_profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_export_function_is_async():
    import app.infra.record_export as mod
    import asyncio
    assert asyncio.iscoroutinefunction(mod.export_record_client)

async def test_export_has_csv_columns():
    import app.infra.record_export as mod
    assert hasattr(mod, "ATTEMPT_CSV_COLUMNS")
