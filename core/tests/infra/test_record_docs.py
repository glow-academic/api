"""Tests for record_docs — docs_record_client."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.infra.record_docs import docs_record_client
pytestmark = pytest.mark.asyncio

async def test_docs_raises_401_when_no_profile(monkeypatch):
    monkeypatch.setattr("app.infra.record_docs.resolve_profile_identity_context", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await docs_record_client(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_docs_returns_response(monkeypatch):
    monkeypatch.setattr("app.infra.record_docs.resolve_profile_identity_context", AsyncMock(return_value=AsyncMock()))
    result = await docs_record_client(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert result.name == "record"

async def test_docs_has_api_operations(monkeypatch):
    monkeypatch.setattr("app.infra.record_docs.resolve_profile_identity_context", AsyncMock(return_value=AsyncMock()))
    result = await docs_record_client(AsyncMock(), AsyncMock(), profile_id=uuid4())
    assert len(result.api_operations) >= 1
