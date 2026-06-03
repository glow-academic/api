"""Tests for export_test_impl — export orchestration."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio

async def test_export_raises_401_when_no_profile(monkeypatch):
    import app.infra.test.export as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    # view='single' needs a test_id to reach the profile-resolution auth
    # check; without it the impl validation-rejects with 400 first.
    with pytest.raises(HTTPException) as exc:
        await mod.export_test_impl(
            pool, redis, profile_id=uuid4(), test_id=uuid4()
        )
    assert exc.value.status_code == 401

async def test_export_function_exists():
    import app.infra.test.export as mod
    assert callable(mod.export_test_impl)

async def test_export_module_has_csv_columns():
    import app.infra.test.export as mod
    csv_attrs = [a for a in dir(mod) if a.endswith("_CSV_COLUMNS") or a.endswith("_COLUMNS")]
    assert len(csv_attrs) >= 1 or hasattr(mod, "PIPE")
