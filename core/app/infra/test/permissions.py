"""Permission helpers + business calculations for benchmark test artifacts.

This module is the test-subsystem mirror of ``app.infra.attempt.permissions``
(the ``enforce_attempt_access_by_*`` family landed for #148/#343/#367). The
test/invocation **mutation** surface — grade, invocation_complete,
invocation_terminate, invocation_run, trace, the whole-test complete, feedback,
and archive — historically keyed its writes purely on a caller-supplied child id
(``invocation_id`` / ``test_invocation_run_id`` / ``grade_id`` / ``test_id``) and
existence-checked it, but never resolved the resource's owner. ``require_auth``
only proves the caller is *some* authenticated profile, so any authenticated
caller could forge a grade onto, force-complete, terminate, bind a run into, or
archive **another user's** benchmark resource (parent-access IDOR / BOLA).

The ownership chain is private (not a catalog):

    test_invocation → group_id → groups_entry.session_id → sessions_mv.profile_id
    test_invocation_runs → test_invocation_id → (as above)
    test_grade → invocation_id → (as above)
    test → test.profile_id (the owner's resource profiles_id, carried directly)

Every ``enforce_test_access_by_*`` helper resolves the caller-supplied id down to
its owning profile and funnels into the **shared** attempt-mutation gate
(``_enforce_attempt_owner_access``) so the test class reaches the SAME
owner-or-super-admin-or-strictly-higher-role-AND-shared-department decision the
attempt subsystem already enforces. Fail-closed: an unresolved requester OR an
unresolved owner denies (403, no write).

READ-OP SAFETY (left unguarded, by design): the test/invocation **reads**
(``/test/invocation_get`` etc.) resolve through ``group_test_impl(profile_id,
session_id)`` — the *caller's own* time-windowed group — so they are already
scoped to the caller. Only the mutators above bypassed the caller's-group
scoping by trusting a caller-supplied child id; those are the ones gated here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg
    from redis.asyncio import Redis

    from app.infra.profile_identity_context import ProfileIdentityContext


def compute_test_status(
    num_chats: int | None,
    num_chats_completed: int | None,
) -> str:
    """Compute a minimal status label from chat completion counts."""
    total = num_chats or 0
    done = num_chats_completed or 0

    if total <= 0:
        return "pending"
    if done <= 0:
        return "running"
    if done >= total:
        return "completed"
    return "running"


# =============================================================================
# Ownership enforcement (mirror of app.infra.attempt.permissions)
# =============================================================================


async def _resolve_invocation_owner(
    pool: asyncpg.Pool,
    redis: Redis,
    invocation_id: UUID | None,
) -> UUID | None:
    """Resolve ``test_invocation → group → session → owner profiles_id``.

    Returns the owner's resource ``profiles_id`` (from ``sessions_mv``) or
    ``None`` when the invocation, its group, or the group's session owner can't
    be resolved — the caller funnels ``None`` into the fail-closed gate.
    """
    if invocation_id is None:
        return None

    from app.tools.entries.groups.get import get_groups
    from app.tools.entries.sessions.get import get_sessions
    from app.tools.entries.test_invocation.get import get_test_invocations

    async with pool.acquire() as conn:
        # ``bypass_cache=True``: this is a security gate, so read the authoritative
        # MV row rather than a possibly-stale cached one. ``test_invocation_mv``
        # derives ``group_id`` via the invocation's call→run→group chain, which is
        # populated by the MV refresh AFTER the create-time cache write-back — a
        # cached row can therefore carry ``group_id=None`` and would
        # (incorrectly) fail-close a legitimate owner. The cache hit is cheap to
        # forgo on a mutation path.
        invs = await get_test_invocations(
            conn, [invocation_id], redis, bypass_cache=True,
        )
        group_id = invs[0].group_id if invs else None
        if group_id is None:
            return None
        groups = await get_groups(conn, [group_id], redis)
        session_id = groups[0].session_id if groups else None
        if session_id is None:
            return None
        sessions = await get_sessions(conn, [session_id], redis)
    return sessions[0].profile_id if sessions else None


async def enforce_test_access_by_invocation(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    invocation_id: UUID | None,
    requester: ProfileIdentityContext | None,
    deny_detail: str = "You don't have access to this test invocation.",
) -> None:
    """Authorize an invocation-id-keyed mutation (grade / invocation_complete / run / trace).

    Resolves ``invocation → group → session → owner`` and applies the shared
    attempt-mutation gate. Mirrors ``enforce_attempt_access_by_attempt``.
    """
    from app.infra.attempt.permissions import _enforce_attempt_owner_access

    owner_profiles_id = await _resolve_invocation_owner(pool, redis, invocation_id)
    await _enforce_attempt_owner_access(
        pool, redis,
        owner_profiles_id=owner_profiles_id,
        requester=requester,
        deny_detail=deny_detail,
    )


async def enforce_test_access_by_run(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    run_id: UUID | None,
    requester: ProfileIdentityContext | None,
    deny_detail: str = "You don't have access to this test invocation run.",
) -> None:
    """Authorize a run-id-keyed mutation (``/test/invocation_terminate``).

    Resolves ``test_invocation_runs → test_invocation_id → invocation owner``
    and applies the shared gate. Direct analogue of the run-keyed ``stop_attempt``
    (M1) fix.
    """
    from app.infra.attempt.permissions import _enforce_attempt_owner_access

    invocation_id: UUID | None = None
    if run_id is not None:
        from app.tools.entries.test_invocation_runs.get import (
            get_test_invocation_runs,
        )

        async with pool.acquire() as conn:
            runs = await get_test_invocation_runs(conn, [run_id], redis)
        invocation_id = runs[0].test_invocation_id if runs else None

    if invocation_id is None:
        # No resolvable parent invocation → no owner → fail closed.
        await _enforce_attempt_owner_access(
            pool, redis, owner_profiles_id=None, requester=requester,
            deny_detail=deny_detail,
        )
        return

    await enforce_test_access_by_invocation(
        pool, redis, invocation_id=invocation_id, requester=requester,
        deny_detail=deny_detail,
    )


async def enforce_test_access_by_grade(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    grade_id: UUID | None,
    requester: ProfileIdentityContext | None,
    deny_detail: str = "You don't have access to this test grade.",
) -> None:
    """Authorize a grade-id-keyed write (``/test/feedback``).

    Resolves ``test_grade → invocation_id → invocation owner`` and applies the
    shared gate. Mirrors ``enforce_attempt_access_by_grade``.
    """
    from app.infra.attempt.permissions import _enforce_attempt_owner_access

    invocation_id: UUID | None = None
    if grade_id is not None:
        from app.tools.entries.test_grade.get import get_test_grades

        async with pool.acquire() as conn:
            grades = await get_test_grades(conn, [grade_id], redis)
        invocation_id = grades[0].invocation_id if grades else None

    if invocation_id is None:
        await _enforce_attempt_owner_access(
            pool, redis, owner_profiles_id=None, requester=requester,
            deny_detail=deny_detail,
        )
        return

    await enforce_test_access_by_invocation(
        pool, redis, invocation_id=invocation_id, requester=requester,
        deny_detail=deny_detail,
    )


async def enforce_test_access_by_group(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    group_id: UUID | None,
    requester: ProfileIdentityContext | None,
    deny_detail: str = "You don't have access to this test group.",
) -> None:
    """Authorize a group-id-keyed mutation (``/test/title``).

    A test ``groups_entry`` has no profile column — it is owned via its
    ``session_id`` (the session that created it). We resolve ``group_id →
    session_id → session.profile_id`` (the owner's resource profiles_id, from
    ``sessions_mv``) and apply the shared attempt-mutation gate. This is the
    test-subsystem mirror of ``enforce_attempt_access_by_group`` — the test
    group chain is per-session-private (see the module docstring), unlike the
    org-shared catalog groups the other ``title`` wrappers rename.

    Fail-closed: if the group, its session, or the session owner can't be
    resolved, the shared gate denies (an unresolved owner is ``None``).
    """
    from app.infra.attempt.permissions import _enforce_attempt_owner_access
    from app.tools.entries.groups.get import get_groups
    from app.tools.entries.sessions.get import get_sessions

    owner_profiles_id: UUID | None = None
    if group_id is not None:
        async with pool.acquire() as conn:
            groups = await get_groups(conn, [group_id], redis)
            session_id = groups[0].session_id if groups else None
            if session_id is not None:
                sessions = await get_sessions(conn, [session_id], redis)
                owner_profiles_id = sessions[0].profile_id if sessions else None

    await _enforce_attempt_owner_access(
        pool, redis,
        owner_profiles_id=owner_profiles_id,
        requester=requester,
        deny_detail=deny_detail,
    )


async def enforce_test_access_by_test(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    test_id: UUID | None,
    requester: ProfileIdentityContext | None,
    deny_detail: str = "You don't have access to this test.",
) -> None:
    """Authorize a test-id-keyed mutation (whole-test ``/test/complete``, archive).

    A ``test_entry`` carries its owner directly (``test.profile_id`` = the
    owner's resource profiles_id), so we resolve it straight off the row and
    apply the shared gate. Fail-closed if the test (or its owner) can't be
    resolved.
    """
    from app.infra.attempt.permissions import _enforce_attempt_owner_access

    owner_profiles_id: UUID | None = None
    if test_id is not None:
        from app.tools.entries.test.get import get_tests

        async with pool.acquire() as conn:
            tests = await get_tests(conn, [test_id], redis)
        owner_profiles_id = tests[0].profile_id if tests else None

    await _enforce_attempt_owner_access(
        pool, redis,
        owner_profiles_id=owner_profiles_id,
        requester=requester,
        deny_detail=deny_detail,
    )
