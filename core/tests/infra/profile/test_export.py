"""Tests for export_profile_impl — export orchestration."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio

async def test_export_raises_401_when_no_profile(monkeypatch):
    import app.infra.profile.export as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc:
        await mod.export_profile_impl(pool, redis, profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_export_function_exists():
    import app.infra.profile.export as mod
    assert callable(mod.export_profile_impl)

async def test_export_module_has_csv_columns():
    import app.infra.profile.export as mod
    csv_attrs = [a for a in dir(mod) if a.endswith("_CSV_COLUMNS") or a.endswith("_COLUMNS")]
    assert len(csv_attrs) >= 1 or hasattr(mod, "PIPE")


# ── Authorization (M5) — the endpoint had NO permission gate + NO role-tier
# scope: a GUEST token could export the whole org directory (verified live).
# These pin: missing capability → 403; permitted callers scope the search to
# roles at/below their tier (superadmin sees all; lower tiers exclude higher).


def _profile(role_level, perms):
    return SimpleNamespace(
        profiles_id=uuid4(), role="r", role_level=role_level, role_permissions=perms,
    )


class _AcqCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *a):
        return False


def _pool():
    pool = AsyncMock()
    pool.acquire = lambda *a, **k: _AcqCM()
    return pool


def _roles():
    # level: lower number = higher privilege. superadmin=0, admin=1, member=2.
    return [
        SimpleNamespace(id=uuid4(), name="superadmin", level=0),
        SimpleNamespace(id=uuid4(), name="admin", level=1),
        SimpleNamespace(id=uuid4(), name="member", level=2),
    ]


async def test_export_blocks_caller_without_permission(monkeypatch):
    """A guest/member lacking profile:export → 403 (was a full PII dump)."""
    import app.infra.profile.export as mod
    monkeypatch.setattr(
        mod, "resolve_profile_identity_context",
        AsyncMock(return_value=_profile(role_level=2, perms=[])),  # no perms
    )
    search = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(mod, "search_profiles", search)
    monkeypatch.setattr(mod, "get_roles", AsyncMock(return_value=_roles()))
    with pytest.raises(HTTPException) as exc:
        await mod.export_profile_impl(_pool(), AsyncMock(), profile_id=uuid4())
    assert exc.value.status_code == 403
    search.assert_not_called()  # never reached the dump


async def test_export_scopes_lower_admin_to_below_tier(monkeypatch):
    """A permitted admin (level 1) excludes strictly-higher roles (superadmin
    level 0) from the export search."""
    import app.infra.profile.export as mod
    roles = _roles()
    super_id = next(r.id for r in roles if r.name == "superadmin")
    monkeypatch.setattr(
        mod, "resolve_profile_identity_context",
        AsyncMock(return_value=_profile(role_level=1, perms=[("profile", "export")])),
    )
    search = AsyncMock(return_value=([], 0))  # empty → early-return, no hydration
    monkeypatch.setattr(mod, "search_profiles", search)
    monkeypatch.setattr(mod, "get_roles", AsyncMock(return_value=roles))
    await mod.export_profile_impl(_pool(), AsyncMock(), profile_id=uuid4())
    _, kwargs = search.call_args
    assert super_id in (kwargs["exclude_role_ids"] or [])  # superadmin excluded


async def test_export_superadmin_excludes_nothing(monkeypatch):
    """Superadmin (level 0) has no strictly-higher role → exclude_role_ids None
    (sees the whole directory, as intended)."""
    import app.infra.profile.export as mod
    monkeypatch.setattr(
        mod, "resolve_profile_identity_context",
        AsyncMock(return_value=_profile(role_level=0, perms=[("profile", "export")])),
    )
    search = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(mod, "search_profiles", search)
    monkeypatch.setattr(mod, "get_roles", AsyncMock(return_value=_roles()))
    await mod.export_profile_impl(_pool(), AsyncMock(), profile_id=uuid4())
    _, kwargs = search.call_args
    assert kwargs["exclude_role_ids"] is None
