"""Tests for export_dashboard_impl — export orchestration."""
import base64
import io
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio


class _FakeAcquireCM:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *a):
        return False


# ---------------------------------------------------------------------------
# IDOR / mass-exposure authz tests for view='dashboard' (#152)
#
# ``export_dashboard_impl`` must scope the attempts dump to the actor's
# ``resolve_visible_profile_ids`` set, mirroring ``dashboard/get.py``. The
# unfiltered full-table dump must no longer be possible: only in-scope
# profiles' attempts may appear in the ZIP.
# ---------------------------------------------------------------------------


def _fake_profile(profiles_id, role_level=1):
    return SimpleNamespace(
        profiles_id=profiles_id, role="member", role_level=role_level,
        department_ids=[],
    )


def _fake_attempt(owner_id):
    return SimpleNamespace(
        attempt_id=uuid4(), profile_id=owner_id, simulation_id=None,
        scenario_ids=[], personas_id=None, cohort_id=None, department_id=None,
        attempt_created_at="2026-01-01T00:00:00Z", practice=False,
        infinite_mode=False, num_chats=1, is_archived=False,
    )


def _patch_dashboard(monkeypatch, *, requester, visible_ids, all_attempts):
    """Wire deps; ``search_attempts`` honors the ``profile_ids`` filter so the
    test exercises real scoping behavior (a filtering black-box)."""
    import app.infra.dashboard.export as mod

    monkeypatch.setattr(
        mod, "resolve_profile_identity_context",
        AsyncMock(return_value=requester),
    )
    monkeypatch.setattr(
        mod, "resolve_visible_profile_ids",
        AsyncMock(return_value=visible_ids),
    )

    captured = {}

    async def _search_attempts(conn, redis, **kwargs):
        captured["profile_ids"] = kwargs.get("profile_ids")
        pids = kwargs.get("profile_ids")
        if pids is None:
            rows = list(all_attempts)
        else:
            allow = set(pids)
            rows = [a for a in all_attempts if a.profile_id in allow]
        return rows, len(rows)

    async def _search_chat_entries(conn, redis, **kwargs):
        return []

    monkeypatch.setattr(mod, "search_attempts", _search_attempts)
    monkeypatch.setattr(mod, "search_chat_entries_internal", _search_chat_entries)
    monkeypatch.setattr(mod, "get_profiles", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_simulations", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_scenarios", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_personas", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_cohorts", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_departments", AsyncMock(return_value=[]))
    return mod, captured


def _pool_redis():
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=lambda *a, **k: _FakeAcquireCM())
    return pool, AsyncMock()


def _zip_attempt_ids(envelope) -> set:
    if not envelope.content:
        return set()
    data = base64.b64decode(envelope.content)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        lines = zf.read("attempts.csv").decode("utf-8").strip().splitlines()
    return {ln.split(",")[0] for ln in lines[1:]}  # skip header; col0 = attempt_id


async def test_dashboard_export_scopes_to_visible_and_excludes_foreign(monkeypatch):
    """Low-role actor's dashboard export contains only in-scope attempts —
    cross-department victim attempts are absent from the ZIP."""
    actor = _fake_profile(uuid4(), role_level=2)
    student = uuid4()
    victim = uuid4()  # not in visible set
    mine = _fake_attempt(student)
    theirs = _fake_attempt(victim)
    mod, captured = _patch_dashboard(
        monkeypatch, requester=actor,
        visible_ids=[actor.profiles_id, student],
        all_attempts=[mine, theirs],
    )
    pool, redis = _pool_redis()
    envelope = await mod.export_dashboard_impl(pool, redis, profile_id=actor.profiles_id)

    # The visible set was passed as the search filter (scope enforced).
    assert captured["profile_ids"] == [actor.profiles_id, student]
    ids = _zip_attempt_ids(envelope)
    assert str(mine.attempt_id) in ids          # in-scope present
    assert str(theirs.attempt_id) not in ids     # foreign victim absent


async def test_dashboard_export_superadmin_sees_all(monkeypatch):
    """role_level 0 (superadmin) → resolve_visible_profile_ids returns the whole
    org, so the full export is preserved for legit admins."""
    admin = _fake_profile(uuid4(), role_level=0)
    a1 = _fake_attempt(uuid4())
    a2 = _fake_attempt(uuid4())
    org_ids = [a1.profile_id, a2.profile_id]
    mod, _captured = _patch_dashboard(
        monkeypatch, requester=admin,
        visible_ids=org_ids, all_attempts=[a1, a2],
    )
    pool, redis = _pool_redis()
    envelope = await mod.export_dashboard_impl(pool, redis, profile_id=admin.profiles_id)
    ids = _zip_attempt_ids(envelope)
    assert {str(a1.attempt_id), str(a2.attempt_id)} <= ids

async def test_export_raises_401_when_no_profile(monkeypatch):
    import app.infra.dashboard.export as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc:
        await mod.export_dashboard_impl(pool, redis, profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_export_function_exists():
    import app.infra.dashboard.export as mod
    assert callable(mod.export_dashboard_impl)

async def test_export_module_has_csv_columns():
    import app.infra.dashboard.export as mod
    csv_attrs = [a for a in dir(mod) if a.endswith("_CSV_COLUMNS") or a.endswith("_COLUMNS")]
    assert len(csv_attrs) >= 1 or hasattr(mod, "PIPE")
