"""Tests for record_export."""
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
# IDOR authz tests for view='record' (#151)
#
# ``export_record_client`` must gate the caller-supplied ``target_profile_id``
# through ``resolve_visible_profile_ids`` (deny if not visible), mirroring the
# on-screen sibling ``record/get.py``.
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


def _patch_record(monkeypatch, *, requester, visible_ids, attempts):
    import app.infra.record_export as mod

    monkeypatch.setattr(
        mod, "resolve_profile_identity_context",
        AsyncMock(return_value=requester),
    )
    monkeypatch.setattr(
        mod, "resolve_visible_profile_ids",
        AsyncMock(return_value=visible_ids),
    )

    async def _search_attempts(conn, redis, **kwargs):
        return attempts, len(attempts)

    async def _search_chats(conn, redis, **kwargs):
        return [], 0

    monkeypatch.setattr(mod, "search_attempts", _search_attempts)
    monkeypatch.setattr(mod, "search_attempt_chats", _search_chats)
    monkeypatch.setattr(mod, "get_profiles", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_simulations", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_scenarios", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_personas", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_cohorts", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_departments", AsyncMock(return_value=[]))
    return mod


def _pool_redis():
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=lambda *a, **k: _FakeAcquireCM())
    return pool, AsyncMock()


def _zip_has_rows(envelope) -> bool:
    """True if the export ZIP actually contains attempt data rows."""
    if not envelope.content:
        return False
    data = base64.b64decode(envelope.content)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        body = zf.read("attempts.csv").decode("utf-8").strip().splitlines()
    return len(body) > 1  # header only == no data


async def test_record_export_blocks_foreign_profile(monkeypatch):
    """Actor exporting a profile NOT in their visible set → 403 (no data)."""
    attacker = _fake_profile(uuid4())
    victim = uuid4()
    mod = _patch_record(
        monkeypatch, requester=attacker,
        visible_ids=[attacker.profiles_id],  # victim not visible
        attempts=[_fake_attempt(victim)],
    )
    pool, redis = _pool_redis()
    with pytest.raises(HTTPException) as exc:
        await mod.export_record_client(
            pool, redis, profile_id=attacker.profiles_id, target_profile_id=victim,
        )
    assert exc.value.status_code == 403


async def test_record_export_allows_self(monkeypatch):
    """Self-export (own profile in visible set) → succeeds with data."""
    me = _fake_profile(uuid4())
    mod = _patch_record(
        monkeypatch, requester=me, visible_ids=[me.profiles_id],
        attempts=[_fake_attempt(me.profiles_id)],
    )
    pool, redis = _pool_redis()
    envelope = await mod.export_record_client(
        pool, redis, profile_id=me.profiles_id, target_profile_id=me.profiles_id,
    )
    assert _zip_has_rows(envelope)


async def test_record_export_allows_instructor_in_scope(monkeypatch):
    """Instructor exporting an in-scope student's record → succeeds."""
    instructor = _fake_profile(uuid4(), role_level=2)
    student = uuid4()
    mod = _patch_record(
        monkeypatch, requester=instructor,
        visible_ids=[instructor.profiles_id, student],
        attempts=[_fake_attempt(student)],
    )
    pool, redis = _pool_redis()
    envelope = await mod.export_record_client(
        pool, redis, profile_id=instructor.profiles_id, target_profile_id=student,
    )
    assert _zip_has_rows(envelope)

async def test_export_raises_401_when_no_profile(monkeypatch):
    import app.infra.record_export as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc:
        await mod.export_record_client(pool, redis, profile_id=uuid4(), target_profile_id=uuid4())
    assert exc.value.status_code == 401

async def test_export_function_is_async():
    import app.infra.record_export as mod
    import asyncio
    assert asyncio.iscoroutinefunction(mod.export_record_client)

async def test_export_has_csv_columns():
    import app.infra.record_export as mod
    assert hasattr(mod, "ATTEMPT_CSV_COLUMNS")
