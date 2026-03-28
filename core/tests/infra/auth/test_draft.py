"""Tests for auth draft — profile check, permission check."""

from uuid import uuid4
import pytest
from app.infra.auth.draft import patch_auth_draft_impl

pytestmark = pytest.mark.asyncio


async def test_draft_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.draft.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await patch_auth_draft_impl(None, None, profile_id=uuid4(), session_id=uuid4(), request=None)
    assert exc_info.value.status_code == 401


async def test_draft_raises_403_for_non_superadmin(monkeypatch):
    from dataclasses import dataclass
    @dataclass
    class P:
        profiles_id: object = None
        role: str = "member"
        name: str = "U"
        group_id: object = None
        department_ids: list = None
    async def mock_resolve(pool, pid, redis, **kw):
        return P(profiles_id=uuid4())
    monkeypatch.setattr("app.infra.auth.draft.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await patch_auth_draft_impl(None, None, profile_id=uuid4(), session_id=uuid4(), request=None)
    assert exc_info.value.status_code == 403


async def test_draft_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.draft.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await patch_auth_draft_impl(None, None, profile_id=uuid4(), session_id=uuid4(), request=None)
    assert "sign in" in exc_info.value.detail.lower()
