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
        "app.infra.test.title",
        "app.infra.invocation.create",
        "app.infra.test.generate",
        "app.infra.test.watch",
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
        "app.infra.test.stop",
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


# =============================================================================
# F1 — /test/stop (invocation-keyed force-stop) — the #372 sibling that had
# ZERO ownership guard on all three of its paths (live / propose / ack).
# =============================================================================


def _wire_stop(monkeypatch):
    """Capture every ``test.stop.completed`` emit + soft-call write so a deny
    can assert NEITHER fired (no stop emitted, no intent staged)."""
    import app.infra.test.stop as mod

    emitted: list[str] = []
    staged: list[UUID] = []

    async def fake_emit(events):
        for e in events:
            emitted.append(e.data.get("invocation_id"))

    async def fake_create_soft(conn, redis, *, call_id, artifact, operation, artifact_id, status, **k):
        if status == "pending":
            staged.append(artifact_id)

        class _S:
            id = call_id

        return _S()

    monkeypatch.setattr(mod, "make_emit", lambda: fake_emit)
    monkeypatch.setattr(mod, "create_soft_call", fake_create_soft)
    return emitted, staged


async def _run_stop(invocation_id, actor_id, *, soft=False, call_id=None):
    from app.infra.test.stop import test_stop_internal_impl

    data = {
        "invocation_id": str(invocation_id),
        "profile_id": str(actor_id),
        "session_id": str(uuid4()),
        "soft": soft,
    }
    # The soft-propose path is driven through the audit wrapper (it mints the
    # call_id); call the impl with audit=False and inject call_id by shimming
    # ``_run`` is internal, so for the propose-path test we exercise the live
    # path (audit=False) which guards identically. The ack path's guard is
    # covered by the live/propose guard since all three call the same helper.
    return await test_stop_internal_impl(data, audit=False)


async def test_stop_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    emitted, staged = _wire_stop(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_stop(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert emitted == []  # no stop signal injected into the victim's room


async def test_stop_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    emitted, staged = _wire_stop(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_stop(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert emitted == []


async def test_stop_fails_closed_on_unresolvable_invocation(monkeypatch):
    actor = uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(actor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=uuid4(), department_in_scope=True,
        invocation_found=False,
    )
    emitted, staged = _wire_stop(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_stop(uuid4(), actor)
    assert exc.value.status_code == 403
    assert emitted == []


async def test_stop_allows_owner(monkeypatch):
    owner, inv = uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    emitted, staged = _wire_stop(monkeypatch)
    result = await _run_stop(inv, owner)
    assert result.success
    assert emitted == [str(inv)]  # the owner's stop emits


async def test_stop_allows_in_scope_instructor(monkeypatch):
    instructor, owner, inv = uuid4(), uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    emitted, staged = _wire_stop(monkeypatch)
    result = await _run_stop(inv, instructor)
    assert result.success
    assert emitted == [str(inv)]


async def test_stop_allows_superadmin_global(monkeypatch):
    super_id, owner, inv = uuid4(), uuid4(), uuid4()
    _no_globals(monkeypatch)
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    emitted, staged = _wire_stop(monkeypatch)
    result = await _run_stop(inv, super_id)
    assert result.success
    assert emitted == [str(inv)]


# =============================================================================
# F2 — test.next (test-id-keyed: drives another user's test execution). A WS
# fire-and-forget handler: a deny EMITS an error and returns WITHOUT touching
# the search/drive (no foreign invocation/group ids leaked, no run advanced).
# =============================================================================


def _wire_next(monkeypatch):
    import app.infra.test.workflows as mod

    searched: list[UUID] = []
    errors: list[str] = []

    async def fake_search(conn, redis, *, test_ids, **k):
        searched.append(test_ids[0])
        return [], 0  # no invocations → benign all-complete on the allow path

    import app.tools.entries.test_invocation.search as search_mod

    monkeypatch.setattr(
        search_mod, "search_test_invocation_entries_internal", fake_search,
    )
    # workflows binds get_redis_client at module scope — keep it off the real
    # client (the patched getters ignore the redis arg anyway).
    monkeypatch.setattr(mod, "get_redis_client", lambda: object())

    async def fake_emit(events):
        for e in events:
            et = getattr(e, "event", None) or (e.get("event") if isinstance(e, dict) else None)
            if et == "test.next.error":
                errors.append(et)

    return searched, errors, fake_emit


async def _run_next(test_id, actor_id, fake_emit):
    from app.infra.test.workflows import test_next_impl

    data = {
        "sid": "sid-1",
        "profile_id": str(actor_id),
        "session_id": str(uuid4()),
        "test_id": str(test_id),
    }
    # _FakePool keeps the gate + search off any real DB/event-loop.
    return await test_next_impl(data, emit=fake_emit, pool=_FakePool())


async def test_next_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    searched, errors, fake_emit = _wire_next(monkeypatch)
    await _run_next(uuid4(), attacker, fake_emit)
    assert searched == []  # the foreign test was never searched/driven
    assert errors  # a forbidden error was emitted to the caller's own room


async def test_next_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    searched, errors, fake_emit = _wire_next(monkeypatch)
    await _run_next(uuid4(), instructor, fake_emit)
    assert searched == []
    assert errors


async def test_next_allows_owner(monkeypatch):
    owner, test_id = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    searched, errors, fake_emit = _wire_next(monkeypatch)
    await _run_next(test_id, owner, fake_emit)
    assert searched == [test_id]  # the owner's test is searched/driven
    assert errors == []


async def test_next_allows_superadmin_global(monkeypatch):
    super_id, owner, test_id = uuid4(), uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    searched, errors, fake_emit = _wire_next(monkeypatch)
    await _run_next(test_id, super_id, fake_emit)
    assert searched == [test_id]
    assert errors == []


# =============================================================================
# F3 — /test/title (group-id-keyed private-group rename). The per-session-
# private title sibling (the other ~18 title wrappers rename org-shared
# catalogs). A deny must NOT delegate to the generic group rename.
# =============================================================================


def _wire_title(monkeypatch):
    import app.infra.test.title as mod

    renamed: list[UUID] = []

    async def fake_title_group(pool, redis, *, artifact_type, **kwargs):
        request = kwargs.get("request")
        gid = getattr(request, "group_id", None) or kwargs.get("group_id")
        renamed.append(gid)
        from app.infra.group.title import TitleGroupResponse

        return TitleGroupResponse.model_construct(
            group_id=gid, group_name_id=uuid4(), title="renamed",
            idempotency_key=None,
        )

    monkeypatch.setattr(mod, "title_group_impl", fake_title_group)
    return renamed


async def _run_title(group_id, actor_id):
    from app.infra.test.title import TitleTestApiRequest, title_test_impl

    return await title_test_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        request=TitleTestApiRequest(group_id=group_id, title="renamed"),
    )


async def test_title_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    renamed = _wire_title(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_title(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert renamed == []  # the foreign group was never renamed


async def test_title_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    renamed = _wire_title(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_title(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert renamed == []


async def test_title_fails_closed_on_unresolvable_group(monkeypatch):
    # Owner resolves to None (no session) → fail-closed.
    actor = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(actor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=None, department_in_scope=True)
    renamed = _wire_title(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_title(uuid4(), actor)
    assert exc.value.status_code == 403
    assert renamed == []


async def test_title_allows_owner(monkeypatch):
    owner, gid = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    renamed = _wire_title(monkeypatch)
    result = await _run_title(gid, owner)
    assert result.group_id == gid
    assert renamed == [gid]


async def test_title_allows_superadmin_global(monkeypatch):
    super_id, owner, gid = uuid4(), uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    renamed = _wire_title(monkeypatch)
    result = await _run_title(gid, super_id)
    assert result.group_id == gid
    assert renamed == [gid]


# =============================================================================
# F5 — /test/invocation/create (test-id-keyed child bind, the chat_create C1
# shape). A deny must NOT mint a run/call/invocation grafted under the foreign
# test.
# =============================================================================


def _wire_invocation_create(monkeypatch):
    import app.infra.invocation.create as mod

    bound: list[UUID] = []

    async def fake_resolve_group(pool, redis, **k):
        from types import SimpleNamespace

        return SimpleNamespace(group_id=uuid4())

    async def fake_has_permission(*a, **k):
        return True

    async def fake_get_tests(conn, ids, redis, *a, **k):
        from app.tools.entries.test.types import GetTestResponse

        return [GetTestResponse.model_construct(test_id=ids[0])]

    async def fake_get_groups(conn, ids, redis, *a, **k):
        from app.tools.entries.groups.types import GetGroupResponse

        return [GetGroupResponse.model_construct(group_id=ids[0], session_id=uuid4())]

    async def fake_create(conn, redis, **k):
        class _C:
            id = uuid4()

        return _C()

    async def fake_create_invocation(conn, redis, *, test_id, **k):
        bound.append(test_id)

        class _R:
            id = uuid4()

        return _R()

    async def fake_refresh(*a, **k):
        return None

    monkeypatch.setattr("app.infra.group.resolve.resolve_group_impl", fake_resolve_group)
    monkeypatch.setattr(mod, "has_permission", lambda *a, **k: True)
    monkeypatch.setattr(mod, "get_tests", fake_get_tests)
    monkeypatch.setattr(mod, "get_groups", fake_get_groups)
    monkeypatch.setattr(mod, "create_run", fake_create)
    monkeypatch.setattr(mod, "create_call", fake_create)
    monkeypatch.setattr(mod, "create_test_invocation", fake_create_invocation)
    monkeypatch.setattr(mod, "refresh_invocation_impl", fake_refresh)
    return bound


async def _run_invocation_create(test_id, actor_id):
    from app.infra.invocation.create import (
        CreateInvocationApiRequest,
        create_invocation_impl,
    )

    return await create_invocation_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        request=CreateInvocationApiRequest(test_id=test_id),
    )


async def test_invocation_create_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    bound = _wire_invocation_create(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_invocation_create(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert bound == []  # no invocation grafted under the foreign test


async def test_invocation_create_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    bound = _wire_invocation_create(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_invocation_create(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert bound == []


async def test_invocation_create_allows_owner(monkeypatch):
    owner, test_id = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    bound = _wire_invocation_create(monkeypatch)
    result = await _run_invocation_create(test_id, owner)
    assert result.invocation_id is not None
    assert bound == [test_id]


async def test_invocation_create_allows_superadmin_global(monkeypatch):
    super_id, owner, test_id = uuid4(), uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    bound = _wire_invocation_create(monkeypatch)
    result = await _run_invocation_create(test_id, super_id)
    assert result.invocation_id is not None
    assert bound == [test_id]


# =============================================================================
# G2 — /test/generate (client-supplied group_id-keyed LLM generation). The
# guardrail-MISSED op: holding ``test:generate`` is a role check, NOT ownership.
# A deny must raise 403 BEFORE prepare_generation runs — so no run/call is
# minted in the victim's group and no provider cost is burned.
# =============================================================================


def _wire_generate(monkeypatch):
    import app.infra.test.generate as mod

    prepared: list = []

    async def fake_prepare(*a, **k):
        prepared.append(k.get("group_id"))

        class _P:
            run_id = uuid4()
            dispatches = []
            resource_types = []
        return _P()

    async def fake_run(*a, **k):
        class _R:
            produced_media = []
        return _R()

    async def fake_socket_owner(*a, **k):
        return "sid-1"

    # ``has_permission`` is the ONLY pre-existing gate — let it pass so the test
    # exercises the NEW ownership gate, not the role check.
    monkeypatch.setattr(mod, "has_permission", lambda *a, **k: True)
    monkeypatch.setattr(mod, "prepare_generation", fake_prepare)
    monkeypatch.setattr(mod, "run_generation_with_refresh", fake_run)
    monkeypatch.setattr(
        "app.infra.websocket.get_socket_owner.get_socket_owner", fake_socket_owner,
    )
    # REGISTRY.get("test") returns the real test config on the allow path; the
    # deny path raises before it is consulted. No patch needed.
    return prepared


def _profile_with_profiles(profiles_id, role, role_level):
    # generate's kicker path reads profile.profiles_id; ``_profile`` already
    # populates it (frozen dataclass), so this is just a clarity alias.
    return _profile(profiles_id, role, role_level)


async def _run_generate(group_id, actor_id, actor):
    from app.infra.test.generate import generate_test_impl

    return await generate_test_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        group_id=group_id, sid="sid-1", wait_for_complete=True,
    )


async def test_generate_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    actor = _profile_with_profiles(attacker, "member", 1)
    _wire_resolve_profile(monkeypatch, actor)
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    prepared = _wire_generate(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_generate(uuid4(), attacker, actor)
    assert exc.value.status_code == 403
    assert prepared == []  # no generation prepared → no run/call, no provider cost


async def test_generate_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    actor = _profile_with_profiles(instructor, "instructional", 2)
    _wire_resolve_profile(monkeypatch, actor)
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    prepared = _wire_generate(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_generate(uuid4(), instructor, actor)
    assert exc.value.status_code == 403
    assert prepared == []


async def test_generate_allows_owner(monkeypatch):
    owner, gid = uuid4(), uuid4()
    actor = _profile_with_profiles(owner, "member", 1)
    _wire_resolve_profile(monkeypatch, actor)
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    prepared = _wire_generate(monkeypatch)
    result = await _run_generate(gid, owner, actor)
    assert result.group_id == str(gid)
    assert prepared == [gid]  # the owner's group IS prepared


async def test_generate_allows_superadmin_global(monkeypatch):
    super_id, owner, gid = uuid4(), uuid4(), uuid4()
    actor = _profile_with_profiles(super_id, "superadmin", 4)
    _wire_resolve_profile(monkeypatch, actor)
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    prepared = _wire_generate(monkeypatch)
    result = await _run_generate(gid, super_id, actor)
    assert result.group_id == str(gid)
    assert prepared == [gid]


# =============================================================================
# G3 — /test/watch (POST one-shot, group_id-keyed run read). watch_runs_impl's
# profile_id was "checked at route" but never gated → read-side IDOR. A deny
# must raise 403 BEFORE subscribing to the victim's run events (no watch).
# =============================================================================


def _wire_watch(monkeypatch):
    import app.infra.test.watch as mod

    watched: list[UUID] = []

    async def fake_watch_runs(pool, redis, *, group_id, **k):
        watched.append(group_id)
        from app.infra._watch import WatchApiResponse

        return WatchApiResponse(group_id=group_id, runs=[])

    monkeypatch.setattr(mod, "watch_runs_impl", fake_watch_runs)
    return watched


async def _run_watch(group_id, actor_id):
    from app.infra.test.watch import watch_test_impl

    return await watch_test_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        group_id=group_id, wait_for_complete=False,
    )


async def test_watch_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    watched = _wire_watch(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_watch(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert watched == []  # never subscribed to the victim's run events


async def test_watch_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    watched = _wire_watch(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_watch(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert watched == []


async def test_watch_fails_closed_on_unresolvable_group(monkeypatch):
    actor = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(actor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=None, department_in_scope=True)
    watched = _wire_watch(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_watch(uuid4(), actor)
    assert exc.value.status_code == 403
    assert watched == []


async def test_watch_allows_owner(monkeypatch):
    owner, gid = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    watched = _wire_watch(monkeypatch)
    result = await _run_watch(gid, owner)
    assert result.group_id == gid
    assert watched == [gid]  # the owner's run IS watched


async def test_watch_allows_superadmin_global(monkeypatch):
    super_id, owner, gid = uuid4(), uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    watched = _wire_watch(monkeypatch)
    result = await _run_watch(gid, super_id)
    assert result.group_id == gid
    assert watched == [gid]


# =============================================================================
# GUARDRAIL — structural assertion that EVERY id-taking mutator in the
# test/invocation class references an ``enforce_test_access_*`` (or attempt's
# group gate, for the title delegate). This is the durable fix: a future op
# added to the class can't silently skip the guard. (#372 grew to T1–T7 and
# STILL missed stop/next/title — this round's F1/F2/F3; F5 is the same shape.)
#
# Approach: a MAINTAINED REGISTRY of (module, impl-function) for every
# test/invocation MUTATOR, asserted via AST against the function's own source
# (plus any module-level helper it calls — e.g. ``_run`` nested inside the
# stop/run/complete impls) so the guard can live in a nested closure. To add a
# NEW mutator: append it to ``_TEST_MUTATORS``. To add a LEGITIMATELY-EXEMPT op
# (e.g. a pure read mislabelled here), add it to ``_GUARD_EXEMPT`` WITH A
# REASON string — the exemption itself is reviewed in the diff.
# =============================================================================


# (module dotted-path, impl function name). Every entry must guard. These are
# the impls behaviourally tested above (T1–T7, F1–F5) PLUS the two ops this PR
# guarded (generate G2 / watch G3). The route-derived completeness test below
# is the durable structural net; this list keeps the per-impl AST assertion for
# the non-route (websocket) handlers and as belt-and-suspenders for the rest.
_TEST_MUTATORS: list[tuple[str, str]] = [
    ("app.infra.test.grade", "create_grade_impl"),                       # T1
    ("app.infra.test.invocation.complete", "test_invocation_complete_internal_impl"),  # T2
    ("app.infra.test.run", "test_run_internal_impl"),                    # T4 run
    ("app.infra.test.trace", "test_trace_internal_impl"),                # T4 trace
    ("app.infra.test.complete", "test_complete_internal_impl"),          # T5
    ("app.infra.test.feedback", "create_feedback_impl"),                 # T6
    ("app.infra.test.archive", "archive_test_impl"),                     # T7
    ("app.infra.test.stop", "test_stop_internal_impl"),                  # F1
    ("app.infra.test.workflows", "test_next_impl"),                      # F2 (WS, no HTTP route)
    ("app.infra.test.title", "title_test_impl"),                         # F3
    ("app.infra.invocation.create", "create_invocation_impl"),           # F5
    ("app.infra.test.generate", "generate_test_impl"),                   # G2
    ("app.infra.test.watch", "watch_test_impl"),                         # G3
]

# The accepted guard markers — any reference to one of these names inside a
# mutator's source (or a guard-bearing impl it calls, or its own route handler)
# satisfies the guardrail. title_test_impl funnels through the attempt group
# gate via the test-subsystem wrapper, so the test-specific helper is what we
# look for.
_GUARD_MARKERS = {
    "enforce_test_access_by_invocation",
    "enforce_test_access_by_run",
    "enforce_test_access_by_grade",
    "enforce_test_access_by_test",
    "enforce_test_access_by_group",
}

# =============================================================================
# ROUTE-DERIVED COMPLETENESS (G4). The previous meta-test only flagged modules
# that ALREADY contained a guard marker — so a brand-new UNGUARDED op (exactly
# how generate/G2 + watch/G3 slipped through) was invisible. The durable fix:
# enumerate the actual REGISTERED ROUTES (test/invocation/watch surface), and
# assert each one is either guarded (the route handler, or any infra impl it
# calls, references an enforce_test_access_* guard) OR explicitly exempted with
# a reason. A new route with neither FAILS — the guard can no longer be skipped
# silently.
#
# Keyed by (METHOD, PATH). Every route on the test router must appear as either
# guarded-at-runtime (verified structurally) or here, WITH A REASON reviewed in
# the diff. Reads scope through ``group_test_impl`` (the caller's own
# time-windowed group) so they need no child-id ownership gate; creation/start
# take no foreign id; download/draft/decrypt carry their own owner gates.
# =============================================================================

_INFRA_GUARD_PREFIXES = ("app.infra.test.", "app.infra.invocation.")

_ROUTE_GUARD_EXEMPT: dict[tuple[str, str], str] = {
    # ── Reads / refresh: scoped to the caller's OWN group via group_test_impl
    # (the caller's time-windowed group window) — no caller-supplied child id
    # trusted, so no test-ownership gate needed.
    ("POST", "/test/get"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/search"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/invocations"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/invocation_get"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/generations"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/context"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/group"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/benchmark"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/drafts"): "read — group_test_impl scopes to caller's own group",
    ("POST", "/test/refresh"): "cache refresh — group_test_impl scopes to caller's own group",
    ("POST", "/test/export"): "read/export — group_test_impl scopes to caller's own group",
    ("POST", "/test/problem"): "problem report — group_test_impl scopes to caller's own group",
    # ── Creation: no foreign id is trusted (a new test is minted for the caller).
    ("POST", "/test/start"): "creation — mints a new test for the caller; no foreign id consumed",
    # ── Downloads / draft / decrypt: carry their OWN ownership/permission gate
    # (a different guard family than enforce_test_access_*), verified in their
    # own suites — not the test-ownership chain.
    ("POST", "/test/file_download"): "guarded by enforce_upload_owner (upload-owner family) + test:file_download",
    ("POST", "/test/call_download"): "media download — gated by has_permission(test:call_download) + call-belongs check",
    ("POST", "/test/text_download"): "media download — gated by has_permission(test:text_download) + run-belongs check",
    ("POST", "/test/draft"): "guarded by enforce_draft_owner (draft-owner family) + test:invocation_draft",
    ("POST", "/test/decrypt"): "guarded by has_permission(test:invocation_draft) + key-belongs-to-invocation (#268/#270)",
    # ── GET /test/watch: the shared browser-SSE stream sibling of POST /watch.
    # build_artifact_stream_impl is the artifact-agnostic EventSource feed; its
    # group scoping is a separate, pre-existing shared concern (out of scope of
    # the G3 one-shot fix). Documented so this stays visible for a later sweep.
    ("GET", "/test/watch"): (
        "shared browser-SSE stream (build_artifact_stream_impl); group scoping is "
        "a pre-existing cross-artifact concern, separate from the POST /watch (G3) fix"
    ),
}


def _module_func_node(module_name: str, func_name: str):
    """Return the AST node for ``func_name`` defined at top level of
    ``module_name`` (or None)."""
    import ast
    import importlib
    import inspect

    mod = importlib.import_module(module_name)
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == func_name
        ):
            return node
    return None


def _node_references_guard(node) -> bool:
    """True iff ``node`` (and anything nested in it) names a guard marker."""
    import ast

    if node is None:
        return False
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in _GUARD_MARKERS:
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in _GUARD_MARKERS:
            return True
    return False


def _function_references_guard(module_name: str, func_name: str) -> bool:
    """Parse the module's source and return True iff the named function (or any
    function nested inside it) references one of the guard markers by name."""
    return _node_references_guard(_module_func_node(module_name, func_name))


def _build_impl_location_index() -> dict[str, str]:
    """Map every ``*_impl`` function name → its dotted module path, scanning the
    test + invocation infra packages. Used to follow a route handler's calls
    into the impl that actually performs (and guards) the write."""
    import ast
    import importlib
    import pathlib

    index: dict[str, str] = {}
    for pkg in ("app.infra.test", "app.infra.invocation"):
        base = importlib.import_module(pkg)
        root = pathlib.Path(base.__file__).parent
        for py in sorted(root.rglob("*.py")):
            rel = py.relative_to(root).with_suffix("")
            parts = [p for p in rel.parts if p != "__init__"]
            dotted = pkg + ("." + ".".join(parts) if parts else "")
            try:
                tree = ast.parse(py.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name.endswith("_impl")
                ):
                    index.setdefault(node.name, dotted)
    return index


def _called_impl_names(node) -> set[str]:
    """All ``*_impl`` callee names referenced inside ``node``."""
    import ast

    names: set[str] = set()
    if node is None:
        return names
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Name) and f.id.endswith("_impl"):
                names.add(f.id)
            elif isinstance(f, ast.Attribute) and f.attr.endswith("_impl"):
                names.add(f.attr)
    return names


def _route_is_guarded(endpoint_module: str, endpoint_name: str, impl_index: dict[str, str]) -> bool:
    """A route is guarded if its handler — or any test/invocation infra impl the
    handler calls — references an ``enforce_test_access_*`` marker."""
    handler_node = _module_func_node(endpoint_module, endpoint_name)
    if _node_references_guard(handler_node):
        return True  # route-level guard (e.g. /test/invocation_terminate)
    for impl_name in _called_impl_names(handler_node):
        loc = impl_index.get(impl_name)
        if loc and loc.startswith(_INFRA_GUARD_PREFIXES):
            if _function_references_guard(loc, impl_name):
                return True
    return False


def _test_router_routes() -> list[tuple[str, str, str, str]]:
    """(method, path, endpoint_module, endpoint_name) for each registered route
    on the test router (the SOURCE OF TRUTH — actual endpoints, not a list)."""
    from app.routes.test import router

    out: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for r in router.routes:
        ep = getattr(r, "endpoint", None)
        if ep is None:
            continue
        for method in sorted(r.methods or []):
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (method, r.path)
            if key in seen:
                continue
            seen.add(key)
            out.append((method, r.path, ep.__module__, ep.__name__))
    return out


@pytest.mark.parametrize("module_name,func_name", _TEST_MUTATORS)
def test_every_test_mutator_references_a_guard(module_name, func_name):
    """Structural guardrail: each registered test/invocation mutator must
    reference an ``enforce_test_access_*`` guard in its source. Fails loudly if
    a new mutator is added to the registry without a guard (the lesson from
    #372 missing stop/next/title, and #374 missing generate/watch)."""
    assert _function_references_guard(module_name, func_name), (
        f"{module_name}.{func_name} is a test/invocation mutator but does NOT "
        f"reference any of {sorted(_GUARD_MARKERS)} — add the appropriate "
        f"enforce_test_access_* guard (mirror the attempt subsystem), or, if it "
        f"is genuinely exempt, document it in _ROUTE_GUARD_EXEMPT with a reason."
    )


def test_every_test_route_is_guarded_or_exempt():
    """ROUTE-DERIVED completeness (G4). Enumerate every registered route on the
    test/invocation/watch surface and assert each is either guarded (handler or
    an infra impl it calls references ``enforce_test_access_*``) or explicitly
    exempted in ``_ROUTE_GUARD_EXEMPT`` with a reason.

    This is the durable net the prior marker-presence scan lacked: a NEW route
    with no guard AND no exemption fails here — it cannot be silently
    unguarded. (Proven non-vacuous by the sibling tests that remove the guard
    from generate/watch/next and watch this fire.)"""
    impl_index = _build_impl_location_index()
    offenders: list[str] = []
    for method, path, ep_mod, ep_name in _test_router_routes():
        if (method, path) in _ROUTE_GUARD_EXEMPT:
            continue
        if _route_is_guarded(ep_mod, ep_name, impl_index):
            continue
        offenders.append(f"{method} {path} ({ep_mod}.{ep_name})")

    assert not offenders, (
        "These test-surface routes are owner-scoped/mutating but neither "
        "reference an enforce_test_access_* guard (in the handler or an infra "
        f"impl they call) nor appear in _ROUTE_GUARD_EXEMPT: {offenders}. Add "
        "the appropriate enforce_test_access_* guard (mirror the attempt "
        "subsystem), or, if the route is genuinely read-safe / creation-only / "
        "guarded by another owner family, add it to _ROUTE_GUARD_EXEMPT with a "
        "reason."
    )


def test_route_guardrail_catches_a_newly_unguarded_route(monkeypatch):
    """Non-vacuous proof the route-derived net actually fires. Simulate a NEW
    owner-scoped route whose handler/impl has NO guard and is NOT exempt: the
    completeness check must report it as an offender. (Guards the guardrail.)"""
    real = _test_router_routes

    def _with_phantom():
        rows = real()
        rows.append(("POST", "/test/__phantom_unguarded__", "app.infra.test.search", "search_test_impl"))
        return rows

    monkeypatch.setattr(
        "tests.infra.test.test_test_mutation_authz_class._test_router_routes",
        _with_phantom,
    )
    with pytest.raises(AssertionError) as exc:
        test_every_test_route_is_guarded_or_exempt()
    assert "__phantom_unguarded__" in str(exc.value)
