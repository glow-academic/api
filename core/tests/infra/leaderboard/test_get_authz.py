"""Authorization regression tests for the leaderboard read path.

IDOR sibling of #145 (dashboard) and its reports twin. The leaderboard had no
scoping of its own: ``get_leaderboard_impl_cached`` resolved its attempt-chat
context for ALL profiles org-wide whenever no ``target_profile_id`` was given —
only caller-supplied cohort/department filters constrained it. So a restricted
actor (instructor/student) could read other profiles'/cohorts' attempt data via
the leaderboard, a visibility leak.

The fix applies the canonical ``resolve_visible_profile_ids`` policy, mirroring
``dashboard/get.py`` (~101-125) and ``reports/get.py`` (~80-110): a
caller-supplied ``target_profile_id`` is honored only if it is in the actor's
visible set (else 403), and when no target is given the search is restricted to
that visible set. Caller-supplied cohort/department filters are applied ON TOP
of (intersected with) the visibility scope.

Proven both directions:
* org-wide leak — a restricted actor with NO target must NOT see a foreign
  out-of-scope profile's data in the bundle (FAILS pre-fix: foreign profile is
  present in ``resources.profiles``; passes post-fix);
* target IDOR — blocked for a foreign target, allowed for self / in-scope
  student / superadmin;
* superadmin (role_level 0) still sees the full org leaderboard;
* cohort/department filters still narrow WITHIN the visible scope (both reach
  the underlying search, intersected).

Actors/victims/MV data are built via the black-box create helpers; no raw SQL
beyond the standard MV refresh.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.infra.leaderboard.context import resolve_leaderboard_search_context
from app.infra.leaderboard.get import get_leaderboard_impl_cached
from app.infra.leaderboard.types import LeaderboardRequest
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


async def _make_actor(pool, redis_client, *, role_level, department_ids=None):
    """Create a full profile artifact; return ``(artifact_id, resource_id)``.

    ``artifact_id`` is what the read path takes as ``profile_id``;
    ``resource_id`` is the value a caller puts in ``target_profile_id`` and what
    the attempt-chat MV is keyed on.
    """
    from app.tools.artifacts.profile.create import (
        create_profile as create_profile_artifact,
    )
    from app.tools.resources.names.create import create_name
    from app.tools.resources.profiles.create import (
        create_profile as create_profile_resource,
    )
    from app.tools.resources.roles.create import create_role

    tag = unique_tag()
    async with pool.acquire() as conn:
        name = await create_name(conn, f"actor-{tag}", redis_client)
        role = await create_role(
            conn,
            redis_client,
            name=f"Role {tag}",
            description="authz test role",
            level=role_level,
        )
        resource = await create_profile_resource(
            conn,
            redis_client,
            name=f"profile-resource-{tag}",
            description="authz test profile resource",
            role_id=role.id,
            department_ids=list(department_ids or []),
        )
        artifact = await create_profile_artifact(
            conn,
            name_id=name.id,
            role_ids=[role.id],
            department_ids=list(department_ids or []),
            profile_ids=[resource.id],
            redis=redis_client,
        )
    return artifact.id, resource.id


async def _seed_attempt_chat_for(pool, redis_client, profile_resource_id):
    """Seed a session->attempt->chat chain owned by ``profile_resource_id`` and
    refresh the attempt-chat MV so a profile-scoped search returns the row."""
    from app.tools.entries.attempt.create import create_attempt
    from app.tools.entries.attempt_chat.create import create_attempt_chat
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.attempt_chat_bridge.create import (
        create_attempt_chat_bridge,
    )
    from app.tools.entries.chat.create import create_chat
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.persona.create import create_persona
    from app.tools.entries.sessions.create import create_session

    async with pool.acquire() as conn:
        session = await create_session(
            conn, redis_client, profile_id=profile_resource_id
        )
        await create_group(
            conn, redis_client, session_id=session.id, artifact_type="persona"
        )
        persona = await create_persona(conn, redis_client)
        attempt = await create_attempt(
            conn,
            redis_client,
            session_id=session.id,
            user_persona_id=persona.id,
            profiles_id=profile_resource_id,
        )
        chat = await create_chat(conn, redis_client, session_id=session.id)
        ac = await create_attempt_chat(
            conn, redis_client, session_id=session.id, chat_id=chat.id
        )
        await create_attempt_chat_bridge(
            conn,
            redis_client,
            attempt_id=attempt.id,
            attempt_chat_id=ac.id,
            session_id=session.id,
        )
        await refresh_attempt_chat(conn)
    return attempt.id


async def _leaderboard_for(pool, *, actor_artifact_id, target_profile_id=None):
    request = LeaderboardRequest(target_profile_id=target_profile_id)
    bundle, _hit = await get_leaderboard_impl_cached(
        pool,
        request,
        profile_id=actor_artifact_id,
        bypass_cache=True,
    )
    return bundle


# ── The core org-wide leak (no target_profile_id) ───────────────────────────


async def test_restricted_actor_no_target_does_not_see_foreign_profile(
    pool, redis_client
):
    """LEAK: a restricted actor with NO target must see only its visible set.

    Pre-fix the leaderboard read every profile org-wide, so the foreign victim's
    profile appears in the bundle's ``resources.profiles``. Post-fix the search
    is scoped to ``resolve_visible_profile_ids`` (self + same-department
    lower-privilege), so the out-of-department victim is absent.
    """
    from app.tools.resources.departments.create import create_department

    tag = unique_tag()
    async with pool.acquire() as conn:
        dept_a = await create_department(
            conn, name=f"lb-leak-a-{tag}", description="authz", redis=redis_client
        )
        dept_b = await create_department(
            conn, name=f"lb-leak-b-{tag}", description="authz", redis=redis_client
        )

    actor_artifact_id, actor_resource_id = await _make_actor(
        pool, redis_client, role_level=5, department_ids=[dept_a.id]
    )
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=5, department_ids=[dept_b.id]
    )
    await _seed_attempt_chat_for(pool, redis_client, actor_resource_id)
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    bundle = await _leaderboard_for(pool, actor_artifact_id=actor_artifact_id)

    profiles_in_bundle = set(bundle.resources.profiles)
    assert str(victim_resource_id) not in profiles_in_bundle, (
        "org-wide visibility leak: a restricted actor's leaderboard contains a "
        "foreign, out-of-department profile's attempt data"
    )


async def test_superadmin_no_target_sees_org_wide(pool, redis_client):
    """A role_level-0 superadmin's visible set is the whole org → still sees all.

    Confirms the scoping does not regress the broad/superadmin case: a foreign
    profile in a different department is present in the superadmin's bundle.
    """
    from app.tools.resources.departments.create import create_department

    tag = unique_tag()
    async with pool.acquire() as conn:
        dept_b = await create_department(
            conn, name=f"lb-super-b-{tag}", description="authz", redis=redis_client
        )

    superadmin_artifact_id, _ = await _make_actor(
        pool, redis_client, role_level=0
    )
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=5, department_ids=[dept_b.id]
    )
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    bundle = await _leaderboard_for(
        pool, actor_artifact_id=superadmin_artifact_id
    )
    assert str(victim_resource_id) in set(bundle.resources.profiles), (
        "superadmin (role_level 0) should still see the full org leaderboard"
    )


# ── target_profile_id IDOR (mirrors dashboard/reports) ───────────────────────


async def test_low_role_actor_blocked_from_foreign_target(pool, redis_client):
    """BLOCKED: a low-privilege actor requesting a foreign target is denied."""
    actor_artifact_id, _ = await _make_actor(pool, redis_client, role_level=99)
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=99
    )
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    with pytest.raises(HTTPException) as exc:
        await _leaderboard_for(
            pool,
            actor_artifact_id=actor_artifact_id,
            target_profile_id=victim_resource_id,
        )
    assert exc.value.status_code == 403


async def test_self_target_allowed(pool, redis_client):
    """ALLOWED: an actor may always read its own leaderboard scope."""
    actor_artifact_id, actor_resource_id = await _make_actor(
        pool, redis_client, role_level=99
    )
    await _seed_attempt_chat_for(pool, redis_client, actor_resource_id)

    bundle = await _leaderboard_for(
        pool,
        actor_artifact_id=actor_artifact_id,
        target_profile_id=actor_resource_id,
    )
    assert set(bundle.resources.profiles) <= {str(actor_resource_id)}


async def test_instructor_allowed_for_in_scope_student(pool, redis_client):
    """ALLOWED: an instructor may read an in-scope student's leaderboard."""
    from app.tools.resources.departments.create import create_department

    tag = unique_tag()
    async with pool.acquire() as conn:
        department = await create_department(
            conn, name=f"lb-dept-{tag}", description="authz", redis=redis_client
        )

    instructor_artifact_id, _ = await _make_actor(
        pool, redis_client, role_level=2, department_ids=[department.id]
    )
    _student_artifact_id, student_resource_id = await _make_actor(
        pool, redis_client, role_level=5, department_ids=[department.id]
    )
    await _seed_attempt_chat_for(pool, redis_client, student_resource_id)

    bundle = await _leaderboard_for(
        pool,
        actor_artifact_id=instructor_artifact_id,
        target_profile_id=student_resource_id,
    )
    assert bundle is not None


async def test_instructor_blocked_for_out_of_scope_student(pool, redis_client):
    """BLOCKED: an instructor cannot read a student in another department."""
    from app.tools.resources.departments.create import create_department

    tag = unique_tag()
    async with pool.acquire() as conn:
        dept_a = await create_department(
            conn, name=f"lb-a-{tag}", description="authz", redis=redis_client
        )
        dept_b = await create_department(
            conn, name=f"lb-b-{tag}", description="authz", redis=redis_client
        )

    instructor_artifact_id, _ = await _make_actor(
        pool, redis_client, role_level=2, department_ids=[dept_a.id]
    )
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=5, department_ids=[dept_b.id]
    )
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    with pytest.raises(HTTPException) as exc:
        await _leaderboard_for(
            pool,
            actor_artifact_id=instructor_artifact_id,
            target_profile_id=victim_resource_id,
        )
    assert exc.value.status_code == 403


# ── Cohort/department filters compose ON TOP of the visibility scope ─────────


class _CaptureConn:
    """Stub connection that records every ``search_attempt_chats`` query call.

    We only need the first ``fetch`` (the attempt_chat read); it returns no rows
    so the resolver short-circuits the downstream message/resource hydration.
    """

    def __init__(self, capture: dict) -> None:
        self._capture = capture

    async def fetch(self, *args, **kwargs):
        # First fetch is the attempt_chat search; capture its bound params.
        if "attempt_chat_mv" in str(args[0]) and "calls" not in self._capture:
            self._capture["calls"] = args
        return []

    async def fetchval(self, *args, **kwargs):
        return None

    async def execute(self, *args, **kwargs):
        return None


class _CapturePool:
    def __init__(self, capture: dict) -> None:
        self._capture = capture

    def acquire(self):
        capture = self._capture

        class _Ctx:
            async def __aenter__(self_inner):
                return _CaptureConn(capture)

            async def __aexit__(self_inner, *exc):
                return False

        return _Ctx()


async def test_scope_and_cohort_filter_both_reach_search(redis_client):
    """Visible-profile scope AND a caller cohort filter are BOTH passed down.

    The underlying ``search_attempt_chats`` ANDs ``profile_ids`` ($4) with
    ``cohort_ids`` ($6), so passing both narrows the cohort filter WITHIN the
    visibility scope (intersection) rather than replacing it. This asserts the
    resolver forwards both — the scope is not dropped when a cohort is given.

    Modular: deps (conn/redis) are explicit; no live DB. The bound query
    parameters are positional in ``search_attempt_chats``: $4=profile_ids,
    $6=cohort_ids (1-indexed → args[4] and args[6] after the SQL string).
    """
    from uuid import uuid4

    visible_ids = [uuid4(), uuid4()]
    cohort_ids = [uuid4()]
    capture: dict = {}

    await resolve_leaderboard_search_context(
        _CapturePool(capture),  # type: ignore[arg-type]
        redis_client,
        target_profile_id=None,
        visible_profile_ids=visible_ids,
        cohort_ids=cohort_ids,
    )

    args = capture["calls"]
    # search_attempt_chats binds params positionally after the SQL text:
    #   args[0]=SQL, args[1]=attempt_ids ... args[4]=profile_ids, args[6]=cohort_ids
    bound_profile_ids = args[4]
    bound_cohort_ids = args[6]
    assert bound_profile_ids == visible_ids, (
        "visible-profile scope was dropped from the leaderboard search"
    )
    assert bound_cohort_ids == cohort_ids, (
        "caller cohort filter was dropped from the leaderboard search"
    )


async def test_no_target_no_scope_passes_visible_set(redis_client):
    """With no target and no visible set, the search is profile-unconstrained.

    Sanity counterpart: when ``visible_profile_ids`` is None (the only way the
    pre-fix org-wide behavior could occur), ``profile_ids`` is None. The fix
    always supplies the visible set from ``get_leaderboard_impl_cached``, so this
    documents that the resolver itself forwards exactly what it is given.
    """
    capture: dict = {}

    await resolve_leaderboard_search_context(
        _CapturePool(capture),  # type: ignore[arg-type]
        redis_client,
        target_profile_id=None,
        visible_profile_ids=None,
    )

    args = capture["calls"]
    assert args[4] is None
