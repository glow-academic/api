"""Class-wide authorization tests for the test/invocation-mutation family.

The attempt subsystem got ``enforce_attempt_access_by_*`` (R1/M1). Its
test-subsystem mirror — whose impl docstrings repeatedly say "mirrors
/attempt/chat/*" — had NO parallel guard: every test/invocation MUTATOR keyed
its write purely on a caller-supplied child id (``invocation_id`` /
``test_invocation_run_id`` / ``grade_id`` / ``test_id``), existence-checked it,
and wrote — never resolving the resource owner. Any authenticated profile could
therefore:

  T1 — ``/test/grade``              forge a score onto ANY user's invocation
  T2 — ``/test/invocation_complete`` force-complete ANY user's invocation
  T3 — ``/test/invocation_terminate`` finalize ANY user's run (run-keyed, cf. M1)
  T4 — ``/test/invocation_run`` + trace bind a run/trace into ANY user's invocation
  T5 — ``/test/complete``           force-complete ANY user's WHOLE test
  T6 — ``/test/feedback``           attach forged feedback to ANY user's grade
  T7 — ``/test/archive``            archive ANY user's tests

All now route through ``app.infra.test.permissions``:

  * ``enforce_test_access_by_invocation`` (invocation_id → group → session → owner)
  * ``enforce_test_access_by_run``        (run_id → invocation → owner)
  * ``enforce_test_access_by_grade``      (grade_id → invocation → owner)
  * ``enforce_test_access_by_test``       (test_id → test.profile_id owner)

each funnelling into the SAME shared gate the attempt subsystem uses
(``_enforce_attempt_owner_access`` → ``check_attempt_access`` +
``is_profile_in_department_scope``, #148): owner → allowed; super-admin →
global; strictly-higher role in the owner's department → allowed; everything
else → 403 (fail-closed on unresolved owner).

These tests fake the black-box resolvers at their source modules and let the
REAL gate decide. Each deny assertion proves ZERO rows are written (no score
forged, no completion, no termination, no run/trace bound, no feedback, no
archive).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


# ── Actors / fakes ───────────────────────────────────────────────────────────


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


class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def transaction(self):
        return _FakeTxn()


class _FakePool:
    def acquire(self):
        return _FakeConn()


# ── Owner-resolution wiring (shared by all helpers) ───────────────────────────


def _wire_owner_resolution(
    monkeypatch,
    *,
    owner_profile_id: UUID | None,
    department_in_scope: bool,
    invocation_found: bool = True,
    run_found: bool = True,
    grade_found: bool = True,
    test_found: bool = True,
):
    """Fake the ownership-chain resolvers at their source modules so the REAL
    gate decides. The chain is:

      invocation → group → session → owner_profile_id
      run        → invocation (above)
      grade      → invocation (above)
      test       → test.profile_id

    ``*_found=False`` simulates a bogus id (resolver returns []) so the
    fail-closed path can be asserted.
    """
    import app.infra.dashboard.visibility as vis_mod
    import app.tools.entries.groups.get as groups_mod
    import app.tools.entries.sessions.get as sessions_mod
    import app.tools.entries.test.get as test_mod
    import app.tools.entries.test_grade.get as grade_mod
    import app.tools.entries.test_invocation.get as inv_mod
    import app.tools.entries.test_invocation_runs.get as runs_mod

    group_id = uuid4()
    session_id = uuid4()
    invocation_id = uuid4()

    async def fake_get_invocations(conn, ids, redis, *a, **k):
        if not invocation_found:
            return []
        from app.tools.entries.test_invocation.types import GetTestInvocationResponse

        return [GetTestInvocationResponse.model_construct(
            invocation_id=ids[0], group_id=group_id,
        )]

    async def fake_get_groups(conn, ids, redis, *a, **k):
        from app.tools.entries.groups.types import GetGroupResponse

        return [GetGroupResponse.model_construct(group_id=ids[0], session_id=session_id)]

    async def fake_get_sessions(conn, ids, redis, *a, **k):
        from app.tools.entries.sessions.types import GetSessionResponse

        return [GetSessionResponse.model_construct(
            session_id=ids[0], profile_id=owner_profile_id,
        )]

    async def fake_get_runs(conn, ids, redis, *a, **k):
        if not run_found:
            return []
        from app.tools.entries.test_invocation_runs.types import (
            GetTestInvocationRunsResponse,
        )

        return [GetTestInvocationRunsResponse.model_construct(
            id=ids[0], test_invocation_id=invocation_id,
        )]

    async def fake_get_grades(conn, ids, redis, *a, **k):
        if not grade_found:
            return []
        from app.tools.entries.test_grade.types import GetTestGradeResponse

        return [GetTestGradeResponse.model_construct(
            id=ids[0], invocation_id=invocation_id,
        )]

    async def fake_get_tests(conn, ids, redis, *a, **k):
        if not test_found:
            return []
        from app.tools.entries.test.types import GetTestResponse

        return [GetTestResponse.model_construct(
            test_id=ids[0], profile_id=owner_profile_id,
        )]

    async def fake_dept_scope(pool, caller, owner_profiles_id, *a, **k):
        return department_in_scope

    monkeypatch.setattr(inv_mod, "get_test_invocations", fake_get_invocations)
    monkeypatch.setattr(groups_mod, "get_groups", fake_get_groups)
    monkeypatch.setattr(sessions_mod, "get_sessions", fake_get_sessions)
    monkeypatch.setattr(runs_mod, "get_test_invocation_runs", fake_get_runs)
    monkeypatch.setattr(grade_mod, "get_test_grades", fake_get_grades)
    monkeypatch.setattr(test_mod, "get_tests", fake_get_tests)
    monkeypatch.setattr(vis_mod, "is_profile_in_department_scope", fake_dept_scope)


def _wire_resolve_profile(monkeypatch, actor):
    """Patch ``resolve_profile_identity_context`` at the source AND at every impl
    module that ``from ... import``-ed the name at module scope (each binds its
    own reference). The socket-style impls (complete / run / trace / test
    complete) import it lazily inside the function so the source patch covers
    them; ``grade`` binds it at module scope and must be patched directly."""
    import importlib

    import app.infra.profile_identity_context as pic_mod

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    monkeypatch.setattr(pic_mod, "resolve_profile_identity_context", fake_resolve)
    for mod_name in (
        "app.infra.test.grade",
        "app.infra.test.feedback",
        "app.infra.test.archive",
        "app.infra.test.complete",
        "app.infra.test.run",
        "app.infra.test.trace",
        "app.infra.test.invocation.complete",
    ):
        m = importlib.import_module(mod_name)
        if hasattr(m, "resolve_profile_identity_context"):
            monkeypatch.setattr(m, "resolve_profile_identity_context", fake_resolve)


def _no_globals(monkeypatch):
    """Route get_pool/get_redis_client to fakes so the gate + writes never touch
    a real DB. The socket-style impls bind ``get_pool`` / ``get_redis_client`` at
    module scope (``from app.infra.globals import ...``), so patch the source AND
    each impl module's own binding."""
    import importlib

    import app.infra.globals as g

    fake_pool = _FakePool()
    monkeypatch.setattr(g, "get_pool", lambda: fake_pool)
    monkeypatch.setattr(g, "get_redis_client", lambda: object())
    for mod_name in (
        "app.infra.test.invocation.complete",
        "app.infra.test.run",
        "app.infra.test.trace",
        "app.infra.test.complete",
    ):
        m = importlib.import_module(mod_name)
        if hasattr(m, "get_pool"):
            monkeypatch.setattr(m, "get_pool", lambda: fake_pool)
        if hasattr(m, "get_redis_client"):
            monkeypatch.setattr(m, "get_redis_client", lambda: object())


# =============================================================================
# T1 — /test/grade (invocation-keyed score forgery)
# =============================================================================


def _wire_grade(monkeypatch):
    import app.infra.test.grade as mod
    from app.tools.entries.test_grade.create import create_test_grade  # noqa: F401

    written: list[UUID] = []

    async def fake_create_grade(conn, redis, *, invocation_id, **kwargs):
        written.append(invocation_id)

        class _R:
            id = uuid4()

        return _R()

    async def fake_get_invs(conn, ids, redis, *a, **k):
        from app.tools.entries.test_invocation.types import GetTestInvocationResponse
        from datetime import UTC, datetime

        return [GetTestInvocationResponse.model_construct(
            invocation_id=ids[0], group_id=uuid4(), rubric_id=None, test_id=None,
            invocation_created_at=datetime.now(UTC),
        )]

    async def fake_create_call(conn, redis, **k):
        class _C:
            id = uuid4()

        return _C()

    async def fake_refresh(*a, **k):
        return None

    async def fake_invalidate(*a, **k):
        return None

    monkeypatch.setattr(mod, "create_test_grade", fake_create_grade)
    monkeypatch.setattr(mod, "get_test_invocations", fake_get_invs)
    monkeypatch.setattr(mod, "create_call", fake_create_call)
    monkeypatch.setattr(mod, "refresh_test_impl", fake_refresh)
    monkeypatch.setattr(mod, "invalidate_tags", fake_invalidate)
    return written


async def _run_grade(invocation_id, actor_id):
    from app.infra.test.grade import create_grade_impl

    return await create_grade_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        invocation_id=invocation_id, run_id=uuid4(), score=5,
    )


async def test_grade_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    written = _wire_grade(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_grade(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert written == []


async def test_grade_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    written = _wire_grade(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_grade(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert written == []


async def test_grade_fails_closed_on_unresolvable_invocation(monkeypatch):
    actor = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(actor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=uuid4(), department_in_scope=True,
        invocation_found=False,
    )
    written = _wire_grade(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_grade(uuid4(), actor)
    assert exc.value.status_code == 403
    assert written == []


async def test_grade_allows_owner(monkeypatch):
    owner, inv = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    written = _wire_grade(monkeypatch)
    result = await _run_grade(inv, owner)
    assert result["success"]
    assert written == [inv]


async def test_grade_allows_in_scope_instructor(monkeypatch):
    instructor, owner, inv = uuid4(), uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    written = _wire_grade(monkeypatch)
    result = await _run_grade(inv, instructor)
    assert result["success"]
    assert written == [inv]


async def test_grade_allows_superadmin_global(monkeypatch):
    super_id, owner, inv = uuid4(), uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    written = _wire_grade(monkeypatch)
    result = await _run_grade(inv, super_id)
    assert result["success"]
    assert written == [inv]


# =============================================================================
# T2 — /test/invocation_complete (invocation-keyed force-complete)
# =============================================================================


def _wire_invocation_complete(monkeypatch):
    import app.infra.test.invocation.complete as mod

    completed: list[UUID] = []

    class _Result:
        id = uuid4()

    async def fake_create_completion(conn, redis, *, invocation_id, **k):
        completed.append(invocation_id)
        return _Result()

    async def fake_get_invs(conn, ids, redis, *a, **k):
        from app.tools.entries.test_invocation.types import GetTestInvocationResponse

        return [GetTestInvocationResponse.model_construct(
            invocation_id=ids[0], group_id=uuid4(),
        )]

    async def fake_get_groups(conn, ids, redis, *a, **k):
        from app.tools.entries.groups.types import GetGroupResponse

        return [GetGroupResponse.model_construct(group_id=ids[0], session_id=uuid4())]

    async def fake_create(conn, redis, **k):
        class _C:
            id = uuid4()

        return _C()

    async def fake_refresh(*a, **k):
        return None

    import app.tools.entries.calls.create as calls_mod
    import app.tools.entries.groups.get as groups_mod
    import app.tools.entries.runs.create as runs_mod
    import app.tools.entries.test_invocation.get as inv_mod
    import app.tools.entries.test_invocation_completion.create as compl_mod
    import app.infra.invocation.refresh as refresh_mod

    monkeypatch.setattr(compl_mod, "create_test_invocation_completion", fake_create_completion)
    # The guard + audit-group resolution at module scope also call get_test_invocations;
    # they're patched globally by _wire_owner_resolution, but the in-runner import
    # binds the source module too — patch it here for the runner's own resolve.
    monkeypatch.setattr(inv_mod, "get_test_invocations", fake_get_invs)
    monkeypatch.setattr(groups_mod, "get_groups", fake_get_groups)
    monkeypatch.setattr(calls_mod, "create_call", fake_create)
    monkeypatch.setattr(runs_mod, "create_run", fake_create)
    monkeypatch.setattr(refresh_mod, "refresh_invocation_impl", fake_refresh)
    return completed


async def _run_invocation_complete(invocation_id, actor_id):
    from app.infra.test.invocation.complete import (
        test_invocation_complete_internal_impl,
    )

    return await test_invocation_complete_internal_impl(
        {
            "test_id": str(uuid4()),
            "test_invocation_id": str(invocation_id),
            "profile_id": str(actor_id),
            "session_id": str(uuid4()),
        },
        audit=False,
    )


async def test_invocation_complete_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    completed = _wire_invocation_complete(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_invocation_complete(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert completed == []


async def test_invocation_complete_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    completed = _wire_invocation_complete(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_invocation_complete(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert completed == []


async def test_invocation_complete_allows_owner(monkeypatch):
    owner, inv = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    completed = _wire_invocation_complete(monkeypatch)
    result = await _run_invocation_complete(inv, owner)
    assert result.success
    assert completed == [inv]


async def test_invocation_complete_allows_superadmin_global(monkeypatch):
    super_id, owner, inv = uuid4(), uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    completed = _wire_invocation_complete(monkeypatch)
    result = await _run_invocation_complete(inv, super_id)
    assert result.success
    assert completed == [inv]


# =============================================================================
# T4 — /test/invocation_run (invocation-keyed run binding)
# =============================================================================


def _wire_run(monkeypatch):
    import app.infra.test.run as mod

    bound: list[UUID] = []

    async def fake_create_runs(conn, redis, *, test_invocation_id, **k):
        bound.append(test_invocation_id)

        class _R:
            id = uuid4()

        return _R()

    async def fake_refresh(*a, **k):
        return None

    # run.py binds ``create_test_invocation_runs`` at module scope.
    monkeypatch.setattr(mod, "create_test_invocation_runs", fake_create_runs)
    monkeypatch.setattr(mod, "refresh_invocation_impl", fake_refresh)
    return bound


async def _run_run(invocation_id, actor_id):
    from app.infra.test.run import test_run_internal_impl

    return await test_run_internal_impl(
        {
            "test_id": str(uuid4()),
            "test_invocation_id": str(invocation_id),
            "run_id": str(uuid4()),
            "profile_id": str(actor_id),
            "session_id": str(uuid4()),
        },
        audit=False,
    )


async def test_invocation_run_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    bound = _wire_run(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_run(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert bound == []


async def test_invocation_run_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    bound = _wire_run(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_run(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert bound == []


async def test_invocation_run_allows_owner(monkeypatch):
    owner, inv = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    bound = _wire_run(monkeypatch)
    result = await _run_run(inv, owner)
    assert result.success
    assert bound == [inv]


# =============================================================================
# T4 — /test/invocation_trace (invocation-keyed trace binding)
# =============================================================================


def _wire_trace(monkeypatch):
    import app.infra.test.trace as mod

    traced: list[UUID] = []

    async def fake_perform(payload, *, profile_id, session_id):
        traced.append(payload.test_invocation_id)
        return str(uuid4())

    monkeypatch.setattr(mod, "_perform_trace", fake_perform)
    return traced


async def _run_trace(invocation_id, actor_id):
    from app.infra.test.trace import test_trace_internal_impl

    return await test_trace_internal_impl(
        {
            "test_id": str(uuid4()),
            "test_invocation_id": str(invocation_id),
            "profile_id": str(actor_id),
            "session_id": str(uuid4()),
        },
        audit=False,
    )


async def test_invocation_trace_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    traced = _wire_trace(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_trace(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert traced == []


async def test_invocation_trace_allows_owner(monkeypatch):
    owner, inv = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    traced = _wire_trace(monkeypatch)
    result = await _run_trace(inv, owner)
    assert result.success
    assert traced == [inv]


# =============================================================================
# T5 — /test/complete (test-keyed whole-test force-complete)
# =============================================================================


def _wire_test_complete(monkeypatch):
    import app.infra.test.complete as mod

    marked: list[UUID] = []

    async def fake_mark(conn, test_id, *, soft=False):
        marked.append(test_id)
        return 1, [uuid4()]

    async def fake_refresh(*a, **k):
        return None

    monkeypatch.setattr(mod, "_mark_all_invocations_complete", fake_mark)
    import app.infra.invocation.refresh as refresh_mod
    monkeypatch.setattr(refresh_mod, "refresh_invocation_impl", fake_refresh)
    return marked


async def _run_test_complete(test_id, actor_id):
    from app.infra.test.complete import test_complete_internal_impl

    return await test_complete_internal_impl(
        {
            "test_id": str(test_id),
            "profile_id": str(actor_id),
            "session_id": str(uuid4()),
        },
        audit=False,
    )


async def test_test_complete_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    marked = _wire_test_complete(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_test_complete(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert marked == []


async def test_test_complete_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    marked = _wire_test_complete(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_test_complete(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert marked == []


async def test_test_complete_fails_closed_on_unresolvable_test(monkeypatch):
    actor = uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(actor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=uuid4(), department_in_scope=True,
        test_found=False,
    )
    marked = _wire_test_complete(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_test_complete(uuid4(), actor)
    assert exc.value.status_code == 403
    assert marked == []


async def test_test_complete_allows_owner(monkeypatch):
    owner, test_id = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    marked = _wire_test_complete(monkeypatch)
    result = await _run_test_complete(test_id, owner)
    assert result.success
    assert marked == [test_id]


async def test_test_complete_allows_superadmin_global(monkeypatch):
    super_id, owner, test_id = uuid4(), uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    marked = _wire_test_complete(monkeypatch)
    result = await _run_test_complete(test_id, super_id)
    assert result.success
    assert marked == [test_id]


# =============================================================================
# T6 — /test/feedback (grade-keyed feedback forgery)
# =============================================================================


def _wire_feedback(monkeypatch):
    import app.infra.test.feedback as mod

    written: list[UUID] = []

    async def fake_create_feedback(conn, redis, *, grade_id, **k):
        written.append(grade_id)

        class _R:
            id = uuid4()

        return _R()

    async def fake_get_sgs(conn, ids, redis, *a, **k):
        class _SG:
            points = 5
            pass_points = 3

        return [_SG()]

    async def fake_search_standards(conn, redis, **k):
        class _S:
            id = uuid4()

        return [_S()]

    async def fake_get_grades(conn, ids, redis, *a, **k):
        from app.tools.entries.test_grade.types import GetTestGradeResponse

        return [GetTestGradeResponse.model_construct(id=ids[0], call_id=uuid4())]

    async def fake_get_calls(conn, ids, redis, *a, **k):
        class _C:
            run_id = uuid4()

        return [_C()]

    async def fake_create_call(conn, redis, **k):
        class _C:
            id = uuid4()

        return _C()

    async def fake_refresh(*a, **k):
        return None

    async def fake_invalidate(*a, **k):
        return None

    monkeypatch.setattr(mod, "create_test_feedback", fake_create_feedback)
    monkeypatch.setattr(mod, "get_standard_groups", fake_get_sgs)
    monkeypatch.setattr(mod, "search_standards", fake_search_standards)
    monkeypatch.setattr(mod, "get_test_grades", fake_get_grades)
    monkeypatch.setattr(mod, "get_calls", fake_get_calls)
    monkeypatch.setattr(mod, "create_call", fake_create_call)
    monkeypatch.setattr(mod, "refresh_test_impl", fake_refresh)
    monkeypatch.setattr(mod, "invalidate_tags", fake_invalidate)
    return written


async def _run_feedback(grade_id, actor_id):
    from app.infra.test.feedback import create_feedback_impl

    return await create_feedback_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        grade_id=grade_id, tool_call_id=uuid4(), standard_group_id=uuid4(),
        score=4, feedback="f", run_id=uuid4(),
    )


async def test_feedback_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    written = _wire_feedback(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_feedback(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert written == []


async def test_feedback_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    written = _wire_feedback(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_feedback(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert written == []


async def test_feedback_fails_closed_on_unresolvable_grade(monkeypatch):
    actor = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(actor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=uuid4(), department_in_scope=True,
        grade_found=False,
    )
    written = _wire_feedback(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_feedback(uuid4(), actor)
    assert exc.value.status_code == 403
    assert written == []


async def test_feedback_allows_owner(monkeypatch):
    owner, grade = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    written = _wire_feedback(monkeypatch)
    result = await _run_feedback(grade, owner)
    assert result["success"]
    assert written == [grade]


# =============================================================================
# T3 — /test/invocation_terminate is route-level (run-keyed). The guard logic
# is covered directly via enforce_test_access_by_run below (T3 + run resolution).
# =============================================================================


async def test_enforce_by_run_blocks_peer_member(monkeypatch):
    from app.infra.test.permissions import enforce_test_access_by_run

    attacker, owner = uuid4(), uuid4()
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    with pytest.raises(HTTPException) as exc:
        await enforce_test_access_by_run(
            _FakePool(), object(),
            run_id=uuid4(), requester=_profile(attacker, "member", 1),
        )
    assert exc.value.status_code == 403


async def test_enforce_by_run_blocks_cross_department_instructor(monkeypatch):
    from app.infra.test.permissions import enforce_test_access_by_run

    instructor, owner = uuid4(), uuid4()
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    with pytest.raises(HTTPException) as exc:
        await enforce_test_access_by_run(
            _FakePool(), object(),
            run_id=uuid4(), requester=_profile(instructor, "instructional", 2),
        )
    assert exc.value.status_code == 403


async def test_enforce_by_run_fails_closed_on_unresolvable_run(monkeypatch):
    from app.infra.test.permissions import enforce_test_access_by_run

    actor = uuid4()
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=uuid4(), department_in_scope=True,
        run_found=False,
    )
    with pytest.raises(HTTPException) as exc:
        await enforce_test_access_by_run(
            _FakePool(), object(),
            run_id=uuid4(), requester=_profile(actor, "instructional", 2),
        )
    assert exc.value.status_code == 403


async def test_enforce_by_run_allows_owner(monkeypatch):
    owner = uuid4()
    from app.infra.test.permissions import enforce_test_access_by_run

    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    # No exception → allowed.
    await enforce_test_access_by_run(
        _FakePool(), object(),
        run_id=uuid4(), requester=_profile(owner, "member", 1),
    )


async def test_enforce_by_run_allows_superadmin_global(monkeypatch):
    super_id, owner = uuid4(), uuid4()
    from app.infra.test.permissions import enforce_test_access_by_run

    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    await enforce_test_access_by_run(
        _FakePool(), object(),
        run_id=uuid4(), requester=_profile(super_id, "superadmin", 4),
    )


async def test_enforce_by_run_denies_none_requester(monkeypatch):
    """Unauthenticated/unresolved requester → fail-closed."""
    from app.infra.test.permissions import enforce_test_access_by_run

    _wire_owner_resolution(monkeypatch, owner_profile_id=uuid4(), department_in_scope=True)
    with pytest.raises(HTTPException) as exc:
        await enforce_test_access_by_run(
            _FakePool(), object(), run_id=uuid4(), requester=None,
        )
    assert exc.value.status_code == 403


# =============================================================================
# T7 — /test/archive (test-keyed bulk archive)
# =============================================================================


def _wire_archive(monkeypatch):
    import app.infra.test.archive as mod

    archived: list[UUID] = []

    async def fake_resolve_group(*a, **k):
        class _G:
            group_id = uuid4()

        return _G()

    async def fake_create(conn, redis, **k):
        class _C:
            id = uuid4()

        return _C()

    async def fake_create_archive(conn, redis, *, test_id, **k):
        archived.append(test_id)

        class _R:
            id = uuid4()

        return _R()

    monkeypatch.setattr(mod, "resolve_group_impl", fake_resolve_group)
    monkeypatch.setattr(mod, "create_run", fake_create)
    monkeypatch.setattr(mod, "create_call", fake_create)
    monkeypatch.setattr(mod, "create_test_archive", fake_create_archive)
    return archived


async def _run_archive(test_ids, actor_id):
    from app.infra.test.archive import archive_test_impl
    from app.infra.test.types import ArchiveTestsRequest

    return await archive_test_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        request=ArchiveTestsRequest(test_ids=test_ids, archived=True),
    )


async def test_archive_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    archived = _wire_archive(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_archive([uuid4()], attacker)
    assert exc.value.status_code == 403
    assert archived == []


async def test_archive_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    archived = _wire_archive(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_archive([uuid4()], instructor)
    assert exc.value.status_code == 403
    assert archived == []


async def test_archive_fails_closed_on_unresolvable_test(monkeypatch):
    actor = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(actor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=uuid4(), department_in_scope=True,
        test_found=False,
    )
    archived = _wire_archive(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_archive([uuid4()], actor)
    assert exc.value.status_code == 403
    assert archived == []


async def test_archive_allows_owner(monkeypatch):
    owner, t = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    archived = _wire_archive(monkeypatch)
    result = await _run_archive([t], owner)
    assert result.updated_count == 1
    assert archived == [t]


async def test_archive_allows_superadmin_global(monkeypatch):
    super_id, owner, t = uuid4(), uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    archived = _wire_archive(monkeypatch)
    result = await _run_archive([t], super_id)
    assert result.updated_count == 1
    assert archived == [t]
