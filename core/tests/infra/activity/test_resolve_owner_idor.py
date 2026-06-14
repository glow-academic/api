"""G1 — cross-user IDOR: problem resolve/unresolve must enforce ownership.

``resolve_activity_impl`` takes a caller-supplied ``problem_id`` and writes the
resolve/unresolve via ``create_resolve`` — reachable from BOTH the HTTP
``POST /system/resolve`` and the WS ``system.activity_resolve`` surfaces.
Problems are owner-scoped via ``profiles_problems_connection``, but neither
surface checked ownership, so any authenticated user could resolve/unresolve
any other user's report and corrupt the admin triage queue.

``_enforce_problem_owner`` (the G1 fix) resolves the problem's owning
``profiles_id`` and enforces it against the requester, with an admin /
super-admin override (they manage the cross-user triage queue). This suite
mirrors the unit-level monkeypatched style of ``test_download_owner_idor.py``
(the sibling ``enforce_*_owner`` IDOR fix) — no DB:

  * a NON-OWNER, non-admin requester is DENIED 403 and NEVER reaches the write;
  * the OWNER (same ``profiles_id``) is ALLOWED;
  * an ADMIN / super-admin (low ``role_level``) is ALLOWED to resolve any
    user's report.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.activity import resolve as resolve_mod

pytestmark = pytest.mark.asyncio

RESOLVE_MODULE = "app.infra.activity.resolve"


class _Pool:
    """Minimal pool whose acquired conn returns a fixed owner from fetchval."""

    def __init__(self, owner_profiles_id):
        self._owner = owner_profiles_id

    class _Conn:
        def __init__(self, owner):
            self._owner = owner

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def fetchval(self, *a, **kw):
            return self._owner

    def acquire(self):
        return self._Conn(self._owner)


class _Requester:
    """The two fields ``_enforce_problem_owner`` reads off the context."""

    def __init__(self, *, profiles_id, role_level):
        self.profiles_id = profiles_id
        self.role_level = role_level


def _patch_requester(monkeypatch, requester):
    async def mock_resolve(pool, profile_id, redis, **kw):
        return requester

    monkeypatch.setattr(
        f"{RESOLVE_MODULE}.resolve_profile_identity_context", mock_resolve
    )


def _arm_write_tripwire(monkeypatch):
    """Fail loudly if the entry-write chain is reached (a denial must short out
    before any group/run/call/resolve is written)."""

    async def must_not(*a, **kw):
        raise AssertionError("must not reach the entry-write chain when denied")

    monkeypatch.setattr(f"{RESOLVE_MODULE}.resolve_group_impl", must_not)


async def test_non_owner_non_admin_is_denied(monkeypatch):
    """A different, non-admin profile resolving someone else's report → 403."""
    owner_profiles_id = uuid4()
    attacker_profiles_id = uuid4()  # different person, NOT an admin

    _patch_requester(
        monkeypatch,
        _Requester(profiles_id=attacker_profiles_id, role_level=2),  # instructional
    )
    _arm_write_tripwire(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        await resolve_mod.resolve_activity_impl(
            _Pool(owner_profiles_id),
            None,
            profile_id=uuid4(),
            session_id=uuid4(),
            problem_id=uuid4(),
            resolved=True,
        )
    assert exc.value.status_code == 403


async def test_owner_passes_guard(monkeypatch):
    """The report's own owner clears the guard (then proceeds to the write)."""
    owner_profiles_id = uuid4()

    _patch_requester(
        monkeypatch,
        _Requester(profiles_id=owner_profiles_id, role_level=2),
    )

    # Owner clears the guard — short-circuit the write chain with a sentinel so
    # the test stays unit-level (no DB) and asserts only that the guard allowed.
    reached = {"write": False}

    async def stop_after_guard(*a, **kw):
        reached["write"] = True
        raise RuntimeError("__guard_passed__")

    monkeypatch.setattr(f"{RESOLVE_MODULE}.resolve_group_impl", stop_after_guard)

    with pytest.raises(RuntimeError, match="__guard_passed__"):
        await resolve_mod.resolve_activity_impl(
            _Pool(owner_profiles_id),
            None,
            profile_id=uuid4(),
            session_id=uuid4(),
            problem_id=uuid4(),
            resolved=True,
        )
    assert reached["write"] is True


@pytest.mark.parametrize("role_level", [0, 1])
async def test_admin_outranks_any_owner(monkeypatch, role_level):
    """Admin (1) / super-admin (0) may resolve ANY user's report."""
    owner_profiles_id = uuid4()
    admin_profiles_id = uuid4()  # NOT the owner

    _patch_requester(
        monkeypatch,
        _Requester(profiles_id=admin_profiles_id, role_level=role_level),
    )

    reached = {"write": False}

    async def stop_after_guard(*a, **kw):
        reached["write"] = True
        raise RuntimeError("__guard_passed__")

    monkeypatch.setattr(f"{RESOLVE_MODULE}.resolve_group_impl", stop_after_guard)

    with pytest.raises(RuntimeError, match="__guard_passed__"):
        await resolve_mod.resolve_activity_impl(
            _Pool(owner_profiles_id),
            None,
            profile_id=uuid4(),
            session_id=uuid4(),
            problem_id=uuid4(),
            resolved=True,
        )
    assert reached["write"] is True
