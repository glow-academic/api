"""Tests for export_activity_impl — export orchestration."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio

async def test_export_raises_401_when_no_profile(monkeypatch):
    import app.infra.activity.export as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc:
        await mod.export_activity_impl(pool, redis, profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_export_function_exists():
    import app.infra.activity.export as mod
    assert callable(mod.export_activity_impl)

async def test_export_module_has_csv_columns():
    import app.infra.activity.export as mod
    csv_attrs = [a for a in dir(mod) if a.endswith("_CSV_COLUMNS") or a.endswith("_COLUMNS")]
    assert len(csv_attrs) >= 1 or hasattr(mod, "PIPE")


async def test_export_scopes_per_person_searches_to_visible_profiles(monkeypatch):
    """The per-PERSON entry types (activity / logins / problem reports) must be
    clamped to the caller's visible-profile set — the export used to dump every
    profile's rows across all departments (mass PII leak) while the on-screen
    dashboard scoped them (#144). grants + emulations are org-audit rows the
    dashboard also fetches unscoped, so they stay unscoped here too."""
    import app.infra.activity.export as mod

    visible = [uuid4(), uuid4()]
    seen: dict[str, object] = {}

    def _capture(name):
        async def _f(conn, redis, **kwargs):
            seen[name] = kwargs.get("profile_ids", "ABSENT")
            return []
        return _f

    monkeypatch.setattr(
        mod, "resolve_profile_identity_context",
        AsyncMock(return_value=SimpleNamespace(profiles_id=uuid4(), role_level=2)),
    )
    monkeypatch.setattr(mod, "resolve_visible_profile_ids", AsyncMock(return_value=visible))
    monkeypatch.setattr(mod, "search_activity", _capture("activity"))
    monkeypatch.setattr(mod, "search_logins", _capture("logins"))
    monkeypatch.setattr(mod, "search_problems", _capture("problems"))
    monkeypatch.setattr(mod, "search_grants", _capture("grants"))
    monkeypatch.setattr(mod, "search_emulations", _capture("emulations"))

    class _AcqCM:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *a):
            return False

    pool = AsyncMock()
    pool.acquire = lambda *a, **k: _AcqCM()

    await mod.export_activity_impl(pool, AsyncMock(), profile_id=uuid4())

    # Per-person PII → clamped to the visible set.
    assert seen["activity"] == visible
    assert seen["logins"] == visible
    assert seen["problems"] == visible
    # Org-level audit → unscoped (mirrors the on-screen context).
    assert seen["grants"] == "ABSENT"
    assert seen["emulations"] == "ABSENT"
