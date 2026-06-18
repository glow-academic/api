"""Tests for export_attempt_impl — export orchestration."""
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


def _fake_pool():
    """A pool whose ``acquire()`` returns a working async context manager."""
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=lambda *a, **k: _FakeAcquireCM())
    return pool


# ---------------------------------------------------------------------------
# IDOR authz tests for view='single' (#150)
#
# ``_export_single_attempt_bytes`` must gate the target attempt via
# ``check_attempt_access`` (own-attempt OR strictly-higher role), mirroring the
# on-screen sibling ``get_attempt_internal``. Blocked actors must NOT receive
# the victim's data; allowed actors get their ZIP.
# ---------------------------------------------------------------------------


def _fake_profile(profiles_id, role="member", role_level=1):
    return SimpleNamespace(profiles_id=profiles_id, role=role, role_level=role_level)


def _fake_attempt(owner_id, attempt_id=None):
    return SimpleNamespace(
        attempt_id=attempt_id or uuid4(),
        profile_id=owner_id,
        simulation_id=None,
        scenario_ids=[],
        personas_id=None,
        attempt_created_at="2026-01-01T00:00:00Z",
        practice=False,
        infinite_mode=False,
        num_chats=0,
        is_archived=False,
    )


def _patch_single(monkeypatch, *, requester, attempts, department_in_scope=True):
    """Wire the single-export deps as params via monkeypatch (black-box).

    ``department_in_scope`` stubs ``is_profile_in_department_scope`` (the
    #152/#148 cross-department gate export now mirrors from get.py): True keeps
    a foreign attempt in-scope (same-department), False puts it out of scope.
    """
    import app.infra.attempt.export as mod

    monkeypatch.setattr(
        mod, "resolve_profile_identity_context",
        AsyncMock(return_value=requester),
    )
    monkeypatch.setattr(
        mod, "is_profile_in_department_scope",
        AsyncMock(return_value=department_in_scope),
    )

    async def _search_attempts(conn, redis, **kwargs):
        return attempts, len(attempts)

    async def _search_chats(conn, redis, **kwargs):
        return [], 0

    async def _search_messages(conn, redis, **kwargs):
        return [], 0

    monkeypatch.setattr(mod, "search_attempts", _search_attempts)
    monkeypatch.setattr(mod, "search_attempt_chats", _search_chats)
    monkeypatch.setattr(mod, "search_attempt_messages", _search_messages)
    monkeypatch.setattr(mod, "get_profiles", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_simulations", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_scenarios", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_personas", AsyncMock(return_value=[]))
    return mod


def _pool_redis():
    return _fake_pool(), AsyncMock()


async def test_single_export_blocks_low_role_foreign_attempt(monkeypatch):
    """Low-role actor exporting another student's attempt → 403 (no data)."""
    victim_owner = uuid4()
    attacker = _fake_profile(uuid4(), role="member", role_level=1)
    mod = _patch_single(
        monkeypatch, requester=attacker,
        attempts=[_fake_attempt(victim_owner)],
    )
    pool, redis = _pool_redis()
    with pytest.raises(HTTPException) as exc:
        await mod._export_single_attempt_bytes(
            pool, redis, profile_id=attacker.profiles_id, attempt_id=uuid4(),
        )
    assert exc.value.status_code == 403


async def test_single_export_allows_owner(monkeypatch):
    """Owner exporting own attempt → succeeds (returns non-empty ZIP)."""
    owner = _fake_profile(uuid4(), role="member", role_level=1)
    mod = _patch_single(
        monkeypatch, requester=owner,
        attempts=[_fake_attempt(owner.profiles_id)],
    )
    pool, redis = _pool_redis()
    data, row_count = await mod._export_single_attempt_bytes(
        pool, redis, profile_id=owner.profiles_id, attempt_id=uuid4(),
    )
    assert row_count == 1
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert "attempts.csv" in zf.namelist()


async def test_single_export_allows_instructor_over_student(monkeypatch):
    """Instructional (higher role) exporting a SAME-DEPARTMENT student's attempt
    → succeeds."""
    instructor = _fake_profile(uuid4(), role="instructional", role_level=2)
    student_owner = uuid4()
    mod = _patch_single(
        monkeypatch, requester=instructor,
        attempts=[_fake_attempt(student_owner)],
        department_in_scope=True,
    )
    pool, redis = _pool_redis()
    data, row_count = await mod._export_single_attempt_bytes(
        pool, redis, profile_id=instructor.profiles_id, attempt_id=uuid4(),
    )
    assert row_count == 1


async def test_single_export_blocks_cross_department_instructor(monkeypatch):
    """Instructional (higher role) exporting a student's attempt in a DIFFERENT
    department → 403. This is the M1 gap: export had dropped the #152/#148
    department-scope gate that get.py/archive.py enforce, so an elevated user in
    Dept A could export a Dept-B student's CSV/ZIP (attempt rows, grades,
    messages, PII) they cannot view on-screen."""
    instructor = _fake_profile(uuid4(), role="instructional", role_level=2)
    student_owner = uuid4()
    mod = _patch_single(
        monkeypatch, requester=instructor,
        attempts=[_fake_attempt(student_owner)],
        department_in_scope=False,
    )
    pool, redis = _pool_redis()
    with pytest.raises(HTTPException) as exc:
        await mod._export_single_attempt_bytes(
            pool, redis, profile_id=instructor.profiles_id, attempt_id=uuid4(),
        )
    assert exc.value.status_code == 403


async def test_single_export_allows_owner_regardless_of_department(monkeypatch):
    """Owner exporting OWN attempt → succeeds even if the dept stub says
    out-of-scope (the gate is skipped for self; own attempts always allowed)."""
    owner = _fake_profile(uuid4(), role="member", role_level=1)
    mod = _patch_single(
        monkeypatch, requester=owner,
        attempts=[_fake_attempt(owner.profiles_id)],
        department_in_scope=False,
    )
    pool, redis = _pool_redis()
    _data, row_count = await mod._export_single_attempt_bytes(
        pool, redis, profile_id=owner.profiles_id, attempt_id=uuid4(),
    )
    assert row_count == 1


async def test_single_export_allows_superadmin(monkeypatch):
    """Superadmin exporting any attempt → succeeds."""
    admin = _fake_profile(uuid4(), role="superadmin", role_level=0)
    mod = _patch_single(
        monkeypatch, requester=admin,
        attempts=[_fake_attempt(uuid4())],
    )
    pool, redis = _pool_redis()
    _data, row_count = await mod._export_single_attempt_bytes(
        pool, redis, profile_id=admin.profiles_id, attempt_id=uuid4(),
    )
    assert row_count == 1

async def test_export_raises_401_when_no_profile(monkeypatch):
    import app.infra.attempt.export as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    # view='single' needs an attempt_id to reach the profile-resolution
    # auth check; without it the impl validation-rejects with 400 first.
    with pytest.raises(HTTPException) as exc:
        await mod.export_attempt_impl(
            pool, redis, profile_id=uuid4(), attempt_id=uuid4()
        )
    assert exc.value.status_code == 401

async def test_export_function_exists():
    import app.infra.attempt.export as mod
    assert callable(mod.export_attempt_impl)

async def test_export_module_has_csv_columns():
    import app.infra.attempt.export as mod
    csv_attrs = [a for a in dir(mod) if a.endswith("_CSV_COLUMNS") or a.endswith("_COLUMNS")]
    assert len(csv_attrs) >= 1 or hasattr(mod, "PIPE")
