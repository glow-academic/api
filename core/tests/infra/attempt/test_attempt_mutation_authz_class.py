"""Class-wide authorization tests for the attempt-mutation family.

Prior point-fixes gated only ``chat_grade`` (#343) and ``archive`` (#337). The
SAME zero/weak-authz bug lived in their write siblings:

  A1 — the grade-annotation writers ``chat_strengths`` / ``chat_improvements`` /
       ``chat_feedback`` (and ``chat_analyses`` / ``chat_hints``) had NO
       authorization: any authenticated profile could annotate ANY student's
       graded chat by passing a ``grade_id`` / ``message_id`` / ``chat_id``.
  A2 — ``complete`` was department-blind, and its terminal-state twin
       ``chat_complete`` had no authz at all.

All now route through ONE shared authorization path in
``app.infra.attempt.permissions``:

  * ``enforce_attempt_access_by_attempt`` (attempt_id → owner)
  * ``enforce_attempt_access_by_chat``    (chat_id   → owner)
  * ``enforce_attempt_access_by_grade``   (grade_id  → chat → owner)
  * ``enforce_attempt_access_by_message`` (message_id→ chat → owner)

each resolving the attempt owner and funnelling into the same gate the read
path uses (``check_attempt_access`` + ``is_profile_in_department_scope``, #148):
owner → allowed; super-admin → global; strictly-higher role in the owner's
department → allowed; everything else → 403 (fail-closed on unresolved owner).

These tests fake the black-box resolvers at their source modules and let the
REAL gate decide. The deny assertions prove zero rows are written.
"""

from __future__ import annotations

from datetime import UTC, datetime
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


def _chat(chat_id: UUID, owner_profile_id: UUID | None):
    from app.tools.entries.attempt_chat.types import GetAttemptChatResponse

    return GetAttemptChatResponse.model_construct(
        chat_id=chat_id, profile_id=owner_profile_id,
    )


def _grade(grade_id: UUID, chat_id: UUID):
    from app.tools.entries.attempt_grade.types import GetAttemptGradeResponse

    return GetAttemptGradeResponse.model_construct(grade_id=grade_id, chat_id=chat_id)


def _message(message_id: UUID, chat_id: UUID | None):
    from app.tools.entries.attempt_message.types import GetAttemptMessageResponse

    return GetAttemptMessageResponse.model_construct(
        message_id=message_id, chat_id=chat_id,
    )


def _wire_owner_resolution(
    monkeypatch,
    *,
    owner_profile_id: UUID | None,
    department_in_scope: bool,
    grade=None,
    message=None,
):
    """Fake the shared helpers' source-module resolvers: chat (always returns a
    chat owned by ``owner_profile_id``), grade→chat, message→chat, and the
    dept-scope query. The real gate then decides."""
    import app.infra.dashboard.visibility as vis_mod
    import app.tools.entries.attempt_chat.search as chat_search_mod
    import app.tools.entries.attempt_grade.get as grade_get_mod
    import app.tools.entries.attempt_message.get as message_get_mod

    target_chat_id = uuid4()

    async def fake_search_chats(conn, redis, **kwargs):
        return ([_chat(target_chat_id, owner_profile_id)], 1)

    async def fake_get_grades(conn, ids, redis, **kwargs):
        return [grade] if grade is not None else []

    async def fake_get_messages(conn, ids, redis, **kwargs):
        return [message] if message is not None else []

    async def fake_dept_scope(pool, caller, owner_profiles_id, *a, **k):
        return department_in_scope

    monkeypatch.setattr(chat_search_mod, "search_attempt_chats", fake_search_chats)
    monkeypatch.setattr(grade_get_mod, "get_attempt_grades", fake_get_grades)
    monkeypatch.setattr(message_get_mod, "get_attempt_messages", fake_get_messages)
    monkeypatch.setattr(vis_mod, "is_profile_in_department_scope", fake_dept_scope)
    return target_chat_id


def _wire_resolve_profile(monkeypatch, actor):
    """Patch ``resolve_profile_identity_context`` at the source AND at every impl
    module that ``from ... import``-ed the name (each binds its own reference)."""
    import importlib

    import app.infra.profile_identity_context as pic_mod

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    monkeypatch.setattr(pic_mod, "resolve_profile_identity_context", fake_resolve)
    for mod_name in (
        "app.infra.attempt.chat_strengths",
        "app.infra.attempt.chat_improvements",
        "app.infra.attempt.chat_feedback",
        "app.infra.attempt.chat_analyses",
        "app.infra.attempt.chat_hints",
        "app.infra.attempt.chat_complete",
        "app.infra.attempt.chat_analysis_common",
    ):
        m = importlib.import_module(mod_name)
        if hasattr(m, "resolve_profile_identity_context"):
            monkeypatch.setattr(m, "resolve_profile_identity_context", fake_resolve)


# ── A1: grade-keyed annotation writers (generate-pipeline impls) ──────────────


def _wire_strength_writer(monkeypatch):
    import app.infra.attempt.chat_strengths as mod
    from app.tools.entries.attempt_strength.types import CreateAttemptStrengthResponse

    written: list[UUID] = []

    async def fake_create(conn, redis, *, grade_id, **kwargs):
        written.append(grade_id)
        return CreateAttemptStrengthResponse(id=uuid4())

    async def fake_refresh(*a, **k):
        return None

    monkeypatch.setattr(mod, "create_attempt_strength", fake_create)
    monkeypatch.setattr(mod, "refresh_attempt_impl", fake_refresh)
    return written


async def _run_strength(grade_id, actor_id):
    from app.infra.attempt.chat_strengths import chat_strengths_attempt_impl

    return await chat_strengths_attempt_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        grade_id=grade_id, message_id=uuid4(), name="n", description="d",
    )


async def test_chat_strengths_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    grade_id = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
        grade=_grade(grade_id, uuid4()),
    )
    written = _wire_strength_writer(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_strength(grade_id, attacker)
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_strengths_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    grade_id = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
        grade=_grade(grade_id, uuid4()),
    )
    written = _wire_strength_writer(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_strength(grade_id, instructor)
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_strengths_allows_in_scope_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    grade_id = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
        grade=_grade(grade_id, uuid4()),
    )
    written = _wire_strength_writer(monkeypatch)
    result = await _run_strength(grade_id, instructor)
    assert result["strength_id"]
    assert written == [grade_id]


async def test_chat_strengths_allows_owner(monkeypatch):
    owner = uuid4()
    grade_id = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
        grade=_grade(grade_id, uuid4()),
    )
    written = _wire_strength_writer(monkeypatch)
    result = await _run_strength(grade_id, owner)
    assert result["strength_id"]
    assert written == [grade_id]


async def test_chat_strengths_allows_superadmin_global(monkeypatch):
    super_id, owner = uuid4(), uuid4()
    grade_id = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(super_id, "superadmin", 4))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
        grade=_grade(grade_id, uuid4()),
    )
    written = _wire_strength_writer(monkeypatch)
    result = await _run_strength(grade_id, super_id)
    assert result["strength_id"]
    assert written == [grade_id]


async def test_chat_strengths_fails_closed_on_unresolvable_grade(monkeypatch):
    """A grade_id that resolves to no chat → no owner → DENIED (fail-closed)."""
    actor = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(actor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=uuid4(), department_in_scope=True,
        grade=None,  # grade not found
    )
    written = _wire_strength_writer(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_strength(uuid4(), actor)
    assert exc.value.status_code == 403
    assert written == []


# ── A1: improvements / feedback / analyses (grade-keyed) deny smoke ───────────


async def test_chat_improvements_blocks_peer_member(monkeypatch):
    import app.infra.attempt.chat_improvements as mod
    from app.tools.entries.attempt_improvement.types import (
        CreateAttemptImprovementResponse,
    )

    written: list[UUID] = []
    attacker, owner = uuid4(), uuid4()
    grade_id = uuid4()

    async def fake_create(conn, redis, *, grade_id, **kwargs):
        written.append(grade_id)
        return CreateAttemptImprovementResponse(id=uuid4())

    monkeypatch.setattr(mod, "create_attempt_improvement", fake_create)
    monkeypatch.setattr(mod, "refresh_attempt_impl", lambda *a, **k: _none())
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
        grade=_grade(grade_id, uuid4()),
    )
    with pytest.raises(HTTPException) as exc:
        await mod.chat_improvements_attempt_impl(
            _FakePool(), object(), profile_id=attacker, session_id=uuid4(),
            grade_id=grade_id, message_id=uuid4(), name="n", description="d",
        )
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_feedback_blocks_peer_member(monkeypatch):
    import app.infra.attempt.chat_feedback as mod
    from app.tools.entries.attempt_feedback.types import CreateAttemptFeedbackResponse

    written: list[UUID] = []
    attacker, owner = uuid4(), uuid4()
    grade_id, standard_id = uuid4(), uuid4()

    async def fake_get_standards(pool, ids, redis, **k):
        from app.tools.resources.standards.types import GetStandardResponse

        return [GetStandardResponse.model_construct(
            id=standard_id, points=3, standard_group_id=None,
        )]

    async def fake_create(conn, redis, *, grade_id, **kwargs):
        written.append(grade_id)
        return CreateAttemptFeedbackResponse(id=uuid4())

    monkeypatch.setattr(mod, "get_standards", fake_get_standards)
    monkeypatch.setattr(mod, "create_attempt_feedback", fake_create)
    monkeypatch.setattr(mod, "refresh_attempt_impl", lambda *a, **k: _none())
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
        grade=_grade(grade_id, uuid4()),
    )
    with pytest.raises(HTTPException) as exc:
        await mod.chat_feedback_attempt_impl(
            _FakePool(), object(), profile_id=attacker, session_id=uuid4(),
            grade_id=grade_id, standard_id=standard_id, feedback="f",
        )
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_analyses_blocks_peer_member(monkeypatch):
    import app.infra.attempt.chat_analyses as mod
    from app.tools.entries.attempt_analysis.types import CreateAttemptAnalysisResponse

    written: list[UUID] = []
    attacker, owner = uuid4(), uuid4()
    grade_id = uuid4()

    async def fake_create(conn, redis, *, grade_id, **kwargs):
        written.append(grade_id)
        return CreateAttemptAnalysisResponse(id=uuid4())

    monkeypatch.setattr(mod, "create_attempt_analysis", fake_create)
    monkeypatch.setattr(mod, "refresh_attempt_impl", lambda *a, **k: _none())
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
        grade=_grade(grade_id, uuid4()),
    )
    with pytest.raises(HTTPException) as exc:
        await mod.chat_analyses_attempt_impl(
            _FakePool(), object(), profile_id=attacker, session_id=uuid4(),
            grade_id=grade_id, content="c",
        )
    assert exc.value.status_code == 403
    assert written == []


# ── A1: hints (message-keyed) ─────────────────────────────────────────────────


async def test_chat_hints_blocks_peer_member(monkeypatch):
    import app.infra.attempt.chat_hints as mod
    from app.tools.entries.attempt_hint.types import CreateAttemptHintResponse

    written: list[UUID] = []
    attacker, owner = uuid4(), uuid4()
    message_id = uuid4()

    async def fake_create(conn, redis, *, message_id, **kwargs):
        written.append(message_id)
        return CreateAttemptHintResponse(id=uuid4())

    monkeypatch.setattr(mod, "create_attempt_hint", fake_create)
    monkeypatch.setattr(mod, "refresh_attempt_impl", lambda *a, **k: _none())
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
        message=_message(message_id, uuid4()),
    )
    with pytest.raises(HTTPException) as exc:
        await mod.chat_hints_attempt_impl(
            _FakePool(), object(), profile_id=attacker, session_id=uuid4(),
            message_id=message_id, hint="h",
        )
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_hints_allows_owner(monkeypatch):
    import app.infra.attempt.chat_hints as mod
    from app.tools.entries.attempt_hint.types import CreateAttemptHintResponse

    written: list[UUID] = []
    owner = uuid4()
    message_id = uuid4()

    async def fake_create(conn, redis, *, message_id, **kwargs):
        written.append(message_id)
        return CreateAttemptHintResponse(id=uuid4())

    monkeypatch.setattr(mod, "create_attempt_hint", fake_create)
    monkeypatch.setattr(mod, "refresh_attempt_impl", lambda *a, **k: _none())
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
        message=_message(message_id, uuid4()),
    )
    result = await mod.chat_hints_attempt_impl(
        _FakePool(), object(), profile_id=owner, session_id=uuid4(),
        message_id=message_id, hint="h",
    )
    assert result["hint_id"]
    assert written == [message_id]


# ── A2 twin: chat_complete (chat-keyed terminal-state flip) ───────────────────


def _wire_chat_complete(monkeypatch):
    import app.infra.attempt.chat_complete as mod
    from app.tools.entries.attempt_chat_completion.types import (
        CreateAttemptChatCompletionResponse,
    )

    completed: list[UUID] = []

    async def fake_create(conn, redis, *, chat_id, **kwargs):
        completed.append(chat_id)
        return CreateAttemptChatCompletionResponse(id=uuid4(), active=True)

    async def fake_refresh(*a, **k):
        return None

    monkeypatch.setattr(mod, "create_attempt_chat_completion", fake_create)
    monkeypatch.setattr(mod, "refresh_attempt_impl", fake_refresh)
    return completed


async def _run_chat_complete(chat_id, actor_id):
    from app.infra.attempt.chat_complete import chat_complete_attempt_impl

    return await chat_complete_attempt_impl(
        _FakePool(), object(), profile_id=actor_id, session_id=uuid4(),
        chat_id=chat_id,
    )


async def test_chat_complete_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
    )
    completed = _wire_chat_complete(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_chat_complete(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert completed == []


async def test_chat_complete_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
    )
    completed = _wire_chat_complete(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_chat_complete(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert completed == []


async def test_chat_complete_allows_owner(monkeypatch):
    owner = uuid4()
    chat_id = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
    )
    completed = _wire_chat_complete(monkeypatch)
    result = await _run_chat_complete(chat_id, owner)
    assert result["completion_id"]
    assert completed == [chat_id]


async def test_chat_complete_allows_in_scope_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    chat_id = uuid4()
    _wire_resolve_profile(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
    )
    completed = _wire_chat_complete(monkeypatch)
    result = await _run_chat_complete(chat_id, instructor)
    assert result["completion_id"]
    assert completed == [chat_id]


# ── Shared HTTP path: run_chat_analysis_write gates all 5 routes ──────────────


async def test_run_chat_analysis_write_blocks_peer_member(monkeypatch):
    """The single shared gate for the HTTP chat-analysis routes denies a
    non-owner before any group resolution / write / create_fn runs."""
    import app.infra.attempt.chat_analysis_common as mod

    attacker, owner = uuid4(), uuid4()
    create_called = {"n": 0}

    async def fake_create_fn(conn, r, soft):
        create_called["n"] += 1
        return {"attempt_strength_entry": [uuid4()]}

    async def fail_group(*a, **k):
        raise AssertionError("group_attempt_impl ran before authz")

    monkeypatch.setattr(mod, "group_attempt_impl", fail_group)
    _wire_resolve_profile(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
    )

    with pytest.raises(HTTPException) as exc:
        await mod.run_chat_analysis_write(
            _FakePool(), object(),
            operation="chat_strengths",
            primary_table="attempt_strength_entry",
            mv_target="attempt_strength_mv",
            profile_id=attacker, session_id=uuid4(), chat_id=uuid4(),
            idempotency_key=None, soft=False, accept=None,
            arguments={}, create_fn=fake_create_fn,
        )
    assert exc.value.status_code == 403
    assert create_called["n"] == 0  # create_fn never ran


async def _none():
    return None
