"""Tests for auth get — derive_flag_key_and_label and 401 handling."""

from uuid import uuid4

import pytest

from app.infra.auth.get import derive_flag_key_and_label, get_auth_impl

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_get_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(*a, **kw):
        return None

    monkeypatch.setattr("app.infra.auth.get.resolve_common_context", mock_resolve)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_auth_impl(None, None, profile_id=uuid4(), auth_id=uuid4())
    assert exc_info.value.status_code == 401


async def test_derive_flag_key_and_label_standard():
    key, label = derive_flag_key_and_label("auth_active")
    assert key == "active"
    assert label == "Active"


async def test_derive_flag_key_and_label_none():
    key, label = derive_flag_key_and_label(None)
    assert key == "unknown"
    assert label == "Unknown"


async def test_derive_flag_key_and_label_compound():
    key, label = derive_flag_key_and_label("auth_some_flag")
    assert key == "some_flag"
    assert label == "Some Flag"
