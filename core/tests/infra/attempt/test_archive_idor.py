"""Authorization (IDOR/BOLA) tests for the attempt *archive* mutate impl.

``archive_attempt_impl`` (POST /attempt/archive) resolves the target attempts
via ``search_attempts``, which is filtered ONLY by the caller-supplied ids /
filters — it does NOT scope to the acting profile. The acting ``profile_id`` is
used solely for ``group_attempt_impl`` (audit linking), whose result is
discarded. Before the fix, any authenticated profile could archive/unarchive
another student's attempts by passing their ``attempt_ids``.

These tests pin the fix: the impl now resolves the requester's role and keeps
only attempts the actor owns or strictly outranks (``check_attempt_access`` —
owner OR strictly-higher role), mirroring ``get_attempt_internal`` and the
media-download gate (issue #148).

Strategy mirrors ``test_download_idor.py``: the impl composes black-box tools
(``resolve_profile_identity_context``, ``search_attempts``,
``create_attempt_archive``, ``group_attempt_impl``). We monkeypatch those at the
``app.infra.attempt.archive`` module namespace so the test is deterministic and
DB-free, build the actors as real ``ProfileIdentityContext`` objects, and let
the real ``check_attempt_access`` decide. A peer-member attacker therefore
archives 0 rows post-fix (FAILS pre-fix: it would archive the victim's attempt);
the owner and a higher role still succeed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

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


def _wire(monkeypatch, *, actor, victim_attempt):
    """Patch the impl's composed tools. ``search_attempts`` always returns the
    victim's attempt (simulating the attacker supplying its id); the real
    ``check_attempt_access`` then decides whether it gets archived. Records the
    attempt_ids actually handed to ``create_attempt_archive``."""
    import app.infra.attempt.archive as mod
    import app.infra.profile_identity_context as pic_mod
    from app.infra.attempt.group import GroupAttemptApiResponse
    from app.tools.entries.attempt_archive.types import CreateAttemptArchiveResponse

    archived_ids: list[UUID] = []

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_search_attempts(conn, redis, **kwargs):
        return ([victim_attempt], 1)

    async def fake_group(pool, redis, **kwargs):
        return GroupAttemptApiResponse(group_id=uuid4())

    async def fake_create_archive(conn, redis, *, attempt_id, **kwargs):
        archived_ids.append(attempt_id)
        return CreateAttemptArchiveResponse(id=uuid4())

    # Patch at the source module so the stub applies whether or not the impl
    # has (re)imported the name — this lets the *blocks* test demonstrate the
    # real BOLA pre-fix (victim's attempt archived) rather than an import error.
    monkeypatch.setattr(
        pic_mod, "resolve_profile_identity_context", fake_resolve
    )
    monkeypatch.setattr(
        mod, "resolve_profile_identity_context", fake_resolve, raising=False
    )
    monkeypatch.setattr(mod, "search_attempts", fake_search_attempts)
    monkeypatch.setattr(mod, "group_attempt_impl", fake_group)
    monkeypatch.setattr(mod, "create_attempt_archive", fake_create_archive)
    return archived_ids


async def _run(*, actor_profile_id, victim_attempt):
    from app.infra.attempt.archive import (
        ArchiveAttemptsRequest,
        archive_attempt_impl,
    )

    request = ArchiveAttemptsRequest(
        archived=True, attempt_ids=[victim_attempt.attempt_id]
    )
    return await archive_attempt_impl(
        _FakePool(),
        object(),
        profile_id=actor_profile_id,
        session_id=uuid4(),
        request=request,
    )


# ─────────────────────────────────────────────────────────────────────────────


async def test_archive_blocks_peer_member(monkeypatch):
    """A non-owner member supplying the victim's attempt id archives 0 rows."""
    attacker_id, owner_id = uuid4(), uuid4()
    victim = _attempt(uuid4(), owner_id)

    actor = _profile(attacker_id, "member", role_level=1)
    archived_ids = _wire(monkeypatch, actor=actor, victim_attempt=victim)

    result = await _run(actor_profile_id=attacker_id, victim_attempt=victim)

    assert result.updated_count == 0
    assert archived_ids == []  # the victim's attempt was NOT archived


async def test_archive_allows_owner(monkeypatch):
    """The attempt owner archives their own attempt — works."""
    owner_id = uuid4()
    victim = _attempt(uuid4(), owner_id)

    actor = _profile(owner_id, "member", role_level=1)
    archived_ids = _wire(monkeypatch, actor=actor, victim_attempt=victim)

    result = await _run(actor_profile_id=owner_id, victim_attempt=victim)

    assert result.updated_count == 1
    assert archived_ids == [victim.attempt_id]


async def test_archive_allows_higher_role(monkeypatch):
    """A strictly-higher role (instructional) archives a student's attempt."""
    instructor_id, owner_id = uuid4(), uuid4()
    victim = _attempt(uuid4(), owner_id)

    actor = _profile(instructor_id, "instructional", role_level=2)
    archived_ids = _wire(monkeypatch, actor=actor, victim_attempt=victim)

    result = await _run(actor_profile_id=instructor_id, victim_attempt=victim)

    assert result.updated_count == 1
    assert archived_ids == [victim.attempt_id]
