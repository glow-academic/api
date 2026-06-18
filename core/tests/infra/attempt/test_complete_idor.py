"""Authorization (IDOR/BOLA) tests for the attempt *complete* mutate impl.

``complete_attempt_impl`` (POST /attempt/complete) writes the terminal
``attempt_completion_entry`` keyed SOLELY by the caller-supplied ``attempt_id``;
the acting ``profile_id`` was used only for ``group_attempt_impl`` (audit
linking) and the post-write refresh. Before the fix, any authenticated profile
could flip another student's attempt to ``completed`` by passing their
``attempt_id`` — the same BOLA closed for the sibling ``POST /attempt/archive``.

These tests pin the fix: the impl now resolves the requester's identity/role and
the attempt's owner, then gates on ``check_attempt_access`` (owner OR
strictly-higher role) — mirroring ``archive_attempt_impl`` and the read side
(``get_attempt_internal`` / media-download gate, issue #148).

Strategy mirrors ``test_archive_idor.py``: the impl composes black-box tools
(``resolve_profile_identity_context``, ``search_attempts``,
``create_attempt_completion``, ``refresh_attempt_impl``). We monkeypatch those at
the ``app.infra.attempt.complete`` module namespace so the test is deterministic
and DB-free, build the actors as real ``ProfileIdentityContext`` objects, and let
the real ``check_attempt_access`` decide. A peer-member attacker is therefore
DENIED (403) and writes 0 completions (FAILS pre-fix: it would complete the
victim's attempt); the owner and a strictly-higher role still succeed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


# ── Actors ───────────────────────────────────────────────────────────────────


def _profile(profiles_id: UUID, role: str, role_level: int):
    from app.infra.profile_identity_context import ProfileIdentityContext

    return ProfileIdentityContext(
        profiles_id=profiles_id,
        name="actor",
        role=role,
        role_name=role,
        role_description="",
        role_artifacts=[],
        primary_email=None,
        emails=[],
        primary_department_id=None,
        department_ids=[],
        settings_id=None,
        request_limit=None,
        request_limit_interval=None,
        is_active=True,
        role_level=role_level,
        role_permissions=[],
    )


def _attempt(attempt_id: UUID, owner_profile_id: UUID):
    from app.tools.entries.attempt.types import GetAttemptResponse

    return GetAttemptResponse(
        attempt_id=attempt_id,
        simulation_id=None,
        profile_id=owner_profile_id,
        role_id=None,
        user_persona_id=None,
        personas_id=None,
        cohort_id=None,
        department_id=None,
        practice=False,
        attempt_created_at=datetime.now(UTC),
        infinite_mode=False,
        num_chats=1,
        is_archived=False,
        is_completed=False,
        scenario_ids=[],
        chat_entry_id=None,
        attempt_chat_id=None,
    )


# ── Fakes for composed black-box tools ────────────────────────────────────────


class _FakeConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakePool:
    """Pool whose .acquire() yields an inert connection — every composed tool
    that would touch the conn is monkeypatched."""

    def acquire(self):
        return _FakeConn()


def _wire(monkeypatch, *, actor, victim_attempt, department_in_scope=True):
    """Patch the impl's composed tools. Owner resolution + the dept-scope query
    now live in the SHARED authz path (``app.infra.attempt.permissions``) that
    complete routes through (the A2 dept-scope fix), so ``search_attempts`` is
    patched at its source module and ``is_profile_in_department_scope`` at the
    visibility module; the real ``check_attempt_access`` then decides whether the
    completion is written. Records the attempt_ids handed to
    ``create_attempt_completion``."""
    import app.infra.attempt.complete as mod
    import app.infra.dashboard.visibility as vis_mod
    import app.infra.profile_identity_context as pic_mod
    import app.tools.entries.attempt.search as attempt_search_mod
    from app.tools.entries.attempt_completion.types import (
        CreateAttemptCompletionResponse,
    )

    completed_ids: list[UUID] = []

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_search_attempts(conn, redis, **kwargs):
        return ([victim_attempt], 1)

    async def fake_dept_scope(pool, caller, owner_profiles_id, *a, **k):
        return department_in_scope

    async def fake_create_completion(conn, redis, *, attempt_id, **kwargs):
        completed_ids.append(attempt_id)
        return CreateAttemptCompletionResponse(id=uuid4())

    async def fake_refresh(pool, redis, **kwargs):
        return None

    monkeypatch.setattr(pic_mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(
        mod, "resolve_profile_identity_context", fake_resolve, raising=False
    )
    # The shared helper imports search_attempts locally — patch at source.
    monkeypatch.setattr(attempt_search_mod, "search_attempts", fake_search_attempts)
    monkeypatch.setattr(vis_mod, "is_profile_in_department_scope", fake_dept_scope)
    monkeypatch.setattr(mod, "create_attempt_completion", fake_create_completion)
    monkeypatch.setattr(mod, "refresh_attempt_impl", fake_refresh)
    return completed_ids


async def _run(*, actor_profile_id, victim_attempt):
    from app.infra.attempt.complete import complete_attempt_impl

    return await complete_attempt_impl(
        _FakePool(),
        object(),
        profile_id=actor_profile_id,
        session_id=uuid4(),
        attempt_id=victim_attempt.attempt_id,
    )


# ─────────────────────────────────────────────────────────────────────────────


async def test_complete_blocks_peer_member(monkeypatch):
    """A non-owner member supplying the victim's attempt id is DENIED (403) and
    writes 0 completions — the IDOR is closed."""
    attacker_id, owner_id = uuid4(), uuid4()
    victim = _attempt(uuid4(), owner_id)

    actor = _profile(attacker_id, "member", role_level=1)
    completed_ids = _wire(monkeypatch, actor=actor, victim_attempt=victim)

    with pytest.raises(HTTPException) as exc:
        await _run(actor_profile_id=attacker_id, victim_attempt=victim)

    assert exc.value.status_code == 403
    assert completed_ids == []  # the victim's attempt was NOT completed


async def test_complete_allows_owner(monkeypatch):
    """The attempt owner completes their own attempt — works."""
    owner_id = uuid4()
    victim = _attempt(uuid4(), owner_id)

    actor = _profile(owner_id, "member", role_level=1)
    completed_ids = _wire(monkeypatch, actor=actor, victim_attempt=victim)

    result = await _run(actor_profile_id=owner_id, victim_attempt=victim)

    assert result["success"] is True
    assert completed_ids == [victim.attempt_id]


async def test_complete_allows_higher_role(monkeypatch):
    """A strictly-higher role (instructional) IN the owner's department completes
    a student's attempt."""
    instructor_id, owner_id = uuid4(), uuid4()
    victim = _attempt(uuid4(), owner_id)

    actor = _profile(instructor_id, "instructional", role_level=2)
    completed_ids = _wire(
        monkeypatch, actor=actor, victim_attempt=victim, department_in_scope=True
    )

    result = await _run(actor_profile_id=instructor_id, victim_attempt=victim)

    assert result["success"] is True
    assert completed_ids == [victim.attempt_id]


async def test_complete_blocks_cross_department_instructor(monkeypatch):
    """A2: a higher-role instructor whose target is OUTSIDE their department scope
    is DENIED (403) and writes 0 completions — the dept-blind gap is closed."""
    instructor_id, owner_id = uuid4(), uuid4()
    victim = _attempt(uuid4(), owner_id)

    actor = _profile(instructor_id, "instructional", role_level=2)
    completed_ids = _wire(
        monkeypatch, actor=actor, victim_attempt=victim, department_in_scope=False
    )

    with pytest.raises(HTTPException) as exc:
        await _run(actor_profile_id=instructor_id, victim_attempt=victim)

    assert exc.value.status_code == 403
    assert completed_ids == []


async def test_complete_allows_superadmin_global(monkeypatch):
    """A super-admin completes any attempt regardless of department (global)."""
    super_id, owner_id = uuid4(), uuid4()
    victim = _attempt(uuid4(), owner_id)

    actor = _profile(super_id, "superadmin", role_level=4)
    completed_ids = _wire(
        monkeypatch, actor=actor, victim_attempt=victim, department_in_scope=False
    )

    result = await _run(actor_profile_id=super_id, victim_attempt=victim)

    assert result["success"] is True
    assert completed_ids == [victim.attempt_id]


async def test_system_action_bypasses_gate_for_ownerless_attempt(monkeypatch):
    """The background time-limit reaper (``system_action=True``) completes a
    stale attempt whose owner is NULL/unresolvable — the case the per-caller gate
    denies (owner_profiles_id is None → 403 BEFORE the completion row is written,
    so the attempt never went terminal and the reaper re-found + error-spammed it
    every cycle). With the bypass the completion is written and the gate's owner
    resolution is never reached. No request path sets ``system_action`` (it is not
    reachable via the registry dispatch), so user BOLA protection is untouched."""
    from app.infra.attempt.complete import complete_attempt_impl

    ownerless = _attempt(uuid4(), None)  # attempt_mv.profile_id NULL (seed/demo)
    # Resolve the OWNER (would 403 the gate) so we prove the gate is SKIPPED, not
    # passed: if the gate ran, owner=None → 403.
    completed_ids = _wire(monkeypatch, actor=None, victim_attempt=ownerless)

    result = await complete_attempt_impl(
        _FakePool(),
        object(),
        profile_id=uuid4(),
        session_id=uuid4(),
        attempt_id=ownerless.attempt_id,
        system_action=True,
    )

    assert result["success"] is True
    assert completed_ids == [ownerless.attempt_id]  # written despite NULL owner
