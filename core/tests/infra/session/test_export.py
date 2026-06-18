"""Tests for export_session_impl — export orchestration."""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio

async def test_export_raises_401_when_no_profile(monkeypatch):
    import app.infra.session.export as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc:
        await mod.export_session_impl(
            pool, redis, profile_id=uuid4(), target_session_id=uuid4()
        )
    assert exc.value.status_code == 401

async def test_export_function_exists():
    import app.infra.session.export as mod
    assert callable(mod.export_session_impl)

async def test_export_module_has_csv_columns():
    import app.infra.session.export as mod
    csv_attrs = [a for a in dir(mod) if a.endswith("_CSV_COLUMNS") or a.endswith("_COLUMNS")]
    assert len(csv_attrs) >= 1 or hasattr(mod, "PIPE")


# ── Visibility-scope IDOR (sibling of #399 /attempt/export) ───────────────────
#
# export_session_impl took a caller-supplied target_session_id and dumped its
# groups/runs/token-cost WITHOUT the visibility gate its on-screen sibling
# (resolve_session_context) enforces. These pin the fix: a session owned by a
# profile OUTSIDE the caller's visible set is 403; a visible owner / profile-less
# (system) session proceeds.


class _AcqCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *a):
        return False


def _pool():
    pool = AsyncMock()
    pool.acquire = lambda *a, **k: _AcqCM()
    return pool


def _session(owner_profile_id):
    return SimpleNamespace(
        id=uuid4(), profile_id=owner_profile_id, created_at=datetime.now(UTC),
        active=True, mcp=False,
    )


def _wire(monkeypatch, *, owner_profile_id, visible_ids):
    import app.infra.session.export as mod

    monkeypatch.setattr(
        mod, "resolve_profile_identity_context",
        AsyncMock(return_value=SimpleNamespace(profiles_id=uuid4(), role_level=2)),
    )
    monkeypatch.setattr(mod, "get_sessions", AsyncMock(return_value=[_session(owner_profile_id)]))
    monkeypatch.setattr(mod, "resolve_visible_profile_ids", AsyncMock(return_value=visible_ids))
    # Downstream (only reached on the allow path) → empty so the zip builds.
    monkeypatch.setattr(mod, "search_groups", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "search_runs", AsyncMock(return_value=[]))
    return mod


async def test_export_blocks_session_owned_by_invisible_profile(monkeypatch):
    owner_id = uuid4()
    mod = _wire(monkeypatch, owner_profile_id=owner_id, visible_ids=[uuid4()])  # owner NOT visible
    with pytest.raises(HTTPException) as exc:
        await mod.export_session_impl(_pool(), AsyncMock(), profile_id=uuid4(), target_session_id=uuid4())
    assert exc.value.status_code == 403


async def test_export_allows_visible_owner(monkeypatch):
    owner_id = uuid4()
    mod = _wire(monkeypatch, owner_profile_id=owner_id, visible_ids=[owner_id])  # owner visible
    result = await mod.export_session_impl(_pool(), AsyncMock(), profile_id=uuid4(), target_session_id=uuid4())
    assert result is not None  # did not 403


async def test_export_allows_profileless_system_session(monkeypatch):
    mod = _wire(monkeypatch, owner_profile_id=None, visible_ids=[])  # no owner → shared/system
    result = await mod.export_session_impl(_pool(), AsyncMock(), profile_id=uuid4(), target_session_id=uuid4())
    assert result is not None  # profile-less session is allowed (no student to protect)
