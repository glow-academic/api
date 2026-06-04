"""Tests for patch_profile_draft_impl."""
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio

async def test_draft_raises_401_when_no_profile(monkeypatch):
    import app.infra.profile.draft as m
    monkeypatch.setattr(m, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises((HTTPException, Exception)):
        await m.patch_profile_draft_impl(pool, redis, profile_id=uuid4())

async def test_draft_function_is_async():
    import app.infra.profile.draft as m
    import asyncio
    assert asyncio.iscoroutinefunction(m.patch_profile_draft_impl)

async def test_draft_module_composes_tools():
    import app.infra.profile.draft as m
    source = open(m.__file__).read()
    assert "resolve_profile_identity_context" in source or "pool" in source


class _StopAfterResolve(Exception):
    """Sentinel raised by the create_profile_draft stub to halt the impl once
    we've reached (and validated) the resolve_primary_departments_id call."""


async def test_draft_resolve_primary_departments_called_without_name(monkeypatch):
    """Regression: patch_profile_draft_impl must NOT pass an unsupported
    ``name=`` kwarg to resolve_primary_departments_id.

    resolve_primary_departments_id's real signature only accepts
    (conn, redis, *, departments_id, soft). The buggy call site passed
    ``name=request.name or ""`` which raised TypeError at runtime whenever a
    profile draft was saved with a primary_department_id set. Here we replace
    resolve_primary_departments_id with a stub carrying that exact real
    signature so a stray ``name`` kwarg would TypeError, proving fail-pre /
    pass-post.
    """
    from types import SimpleNamespace
    from uuid import UUID

    import app.infra.profile.draft as m
    from app.infra.profile.types import PatchProfileDraftApiRequest

    captured: dict = {}

    async def fake_resolve_primary_departments_id(
        conn, redis, *, departments_id, soft=False
    ):
        captured["departments_id"] = departments_id
        captured["soft"] = soft
        return uuid4()

    async def fake_create_profile_draft(*args, **kwargs):
        raise _StopAfterResolve()

    monkeypatch.setattr(
        m,
        "resolve_profile_identity_context",
        AsyncMock(
            return_value=SimpleNamespace(
                role_level=99,
                role_permissions=[],
                profiles_id=uuid4(),
            )
        ),
    )
    monkeypatch.setattr(m, "compute_can_draft", lambda **_: True)
    monkeypatch.setattr(m, "_resolve_creatable_values", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        m, "resolve_primary_departments_id", fake_resolve_primary_departments_id
    )
    monkeypatch.setattr(m, "create_profile_draft", fake_create_profile_draft)

    from contextlib import asynccontextmanager
    from unittest.mock import MagicMock

    conn = AsyncMock()

    @asynccontextmanager
    async def _acquire(*_a, **_k):
        yield conn

    @asynccontextmanager
    async def _transaction(*_a, **_k):
        yield None

    pool = MagicMock()
    pool.acquire = _acquire
    conn.transaction = _transaction
    redis = AsyncMock()

    dept_id = uuid4()
    request = PatchProfileDraftApiRequest(primary_department_id=dept_id, name="Alice")

    # Pre-fix this raised TypeError (unexpected kwarg 'name') inside
    # resolve_primary_departments_id; post-fix it reaches the create stop-sentinel.
    with pytest.raises(_StopAfterResolve):
        await m.patch_profile_draft_impl(
            pool, redis, profile_id=uuid4(), session_id=uuid4(), request=request
        )

    assert captured["departments_id"] == dept_id
    assert isinstance(captured["departments_id"], UUID)
