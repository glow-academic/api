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


# ── R1: chat/message data-WRITE family (post / answer / voice / audio) ────────
#
# Prior rounds gated the chat-keyed grade/complete writers (A1/A2 above) but
# never swept the DATA-write chat ops, which only existence/FK-checked the raw
# id (#299-era "clean 404") then wrote with the caller's own session — injecting
# into / steering / corrupting another user's conversation. All four now resolve
# the parent attempt's owner and run the SAME shared gate:
#   R1a attempt_message  → enforce_attempt_access_by_chat
#   R1b chat_response    → enforce_attempt_access_by_chat
#   R1c chat_voice       → enforce_attempt_access_by_chat
#   R1d chat_audio       → enforce_attempt_access_by_message
# Deny assertions prove ZERO rows are written (no message / response / audio
# lands, no conversation opened).


def _wire_resolve_profile_for(monkeypatch, actor, mod_names):
    """Patch resolve_profile_identity_context at the source AND at each impl
    module that binds its own reference (the R1 impls live outside the A1/A2
    module set patched by _wire_resolve_profile)."""
    import importlib

    import app.infra.profile_identity_context as pic_mod

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    monkeypatch.setattr(pic_mod, "resolve_profile_identity_context", fake_resolve)
    for mod_name in mod_names:
        m = importlib.import_module(mod_name)
        if hasattr(m, "resolve_profile_identity_context"):
            monkeypatch.setattr(m, "resolve_profile_identity_context", fake_resolve)


# ── R1a: attempt_message (chat-keyed post) ────────────────────────────────────


def _wire_attempt_message(monkeypatch):
    """Fake the whole post chain at its source modules (the impl `from ...
    import`s each create/get lazily inside the function). ``written`` records
    the chat_id passed to the first write — empty on a denied (pre-write) call.
    """
    from app.tools.entries.attempt_message.types import CreateAttemptMessageResponse

    written: list[UUID] = []
    msg_id = uuid4()

    async def fake_create_message(conn, redis, *, chat_id, **kwargs):
        written.append(chat_id)
        return CreateAttemptMessageResponse.model_construct(id=msg_id)

    async def fake_noop_create(conn, redis, **kwargs):
        class _R:
            id = uuid4()
        return _R()

    async def fake_search_messages(conn, redis, **kwargs):
        return ([], 0)

    async def fake_get_chats(conn, ids, redis, **kwargs):
        from app.tools.entries.attempt_chat.types import GetAttemptChatResponse
        return [GetAttemptChatResponse.model_construct(chat_id=ids[0], profile_id=uuid4())]

    async def fake_refresh(*a, **k):
        return None

    import app.tools.entries.attempt_chat.get as chat_get_mod
    import app.tools.entries.attempt_content.create as content_mod
    import app.tools.entries.attempt_message.create as msg_create_mod
    import app.tools.entries.attempt_message.search as msg_search_mod
    import app.tools.entries.attempt_message_completion.create as compl_mod
    import app.infra.attempt.refresh as refresh_mod

    monkeypatch.setattr(chat_get_mod, "get_attempt_chats", fake_get_chats)
    monkeypatch.setattr(msg_create_mod, "create_attempt_message", fake_create_message)
    monkeypatch.setattr(content_mod, "create_attempt_content", fake_noop_create)
    monkeypatch.setattr(msg_search_mod, "search_attempt_messages", fake_search_messages)
    monkeypatch.setattr(compl_mod, "create_attempt_message_completion", fake_noop_create)
    monkeypatch.setattr(refresh_mod, "refresh_attempt_impl", fake_refresh)
    return written


async def _run_attempt_message(chat_id, actor_id):
    from app.infra.attempt.message import attempt_message_internal_impl

    return await attempt_message_internal_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        chat_id=chat_id, text="hi", persona_id=uuid4(),
    )


async def test_attempt_message_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(attacker, "member", 1), ["app.infra.attempt.message"]
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
    )
    written = _wire_attempt_message(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_attempt_message(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert written == []


async def test_attempt_message_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(instructor, "instructional", 2),
        ["app.infra.attempt.message"],
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
    )
    written = _wire_attempt_message(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_attempt_message(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert written == []


async def test_attempt_message_allows_owner(monkeypatch):
    owner = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(owner, "member", 1), ["app.infra.attempt.message"]
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
    )
    written = _wire_attempt_message(monkeypatch)
    result = await _run_attempt_message(uuid4(), owner)
    assert result.message_id
    assert len(written) == 1


async def test_attempt_message_allows_superadmin_global(monkeypatch):
    super_id, owner = uuid4(), uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(super_id, "superadmin", 4), ["app.infra.attempt.message"]
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
    )
    written = _wire_attempt_message(monkeypatch)
    result = await _run_attempt_message(uuid4(), super_id)
    assert result.message_id
    assert len(written) == 1


# ── R1b: chat_response (chat-keyed answer submit) ─────────────────────────────


def _wire_chat_response(monkeypatch):
    import app.infra.attempt.response as mod
    from app.tools.entries.attempt_responses.types import (
        CreateAttemptResponsesResponse,
    )

    written: list[UUID] = []

    async def fake_create(conn, redis, *, chat_id, **kwargs):
        written.append(chat_id)
        return CreateAttemptResponsesResponse.model_construct(id=uuid4())

    async def fake_refresh(*a, **k):
        return None

    # The response impl pulls the pool/redis from globals (not the passed args)
    # — route both to fakes so the gate + write never touch a real DB.
    monkeypatch.setattr(mod, "get_pool", lambda: _FakePool())
    monkeypatch.setattr(mod, "get_redis_client", lambda: object())
    import app.tools.entries.attempt_responses.create as create_mod
    monkeypatch.setattr(create_mod, "create_attempt_responses", fake_create)
    # refresh_attempt_impl is imported lazily inside _run — patch its source.
    import app.infra.attempt.refresh as refresh_mod
    monkeypatch.setattr(refresh_mod, "refresh_attempt_impl", fake_refresh)
    return written


async def _run_chat_response(chat_id, actor_id):
    from app.infra.attempt.response import attempt_response_internal_impl

    return await attempt_response_internal_impl(
        {
            "chat_id": str(chat_id),
            "question_id": str(uuid4()),
            "option_ids": [str(uuid4())],
            "profile_id": str(actor_id),
            "session_id": str(uuid4()),
        },
        audit=False,
    )


async def test_chat_response_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(attacker, "member", 1), ["app.infra.attempt.response"]
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
    )
    written = _wire_chat_response(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_chat_response(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_response_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(instructor, "instructional", 2),
        ["app.infra.attempt.response"],
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
    )
    written = _wire_chat_response(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_chat_response(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_response_allows_owner(monkeypatch):
    owner = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(owner, "member", 1), ["app.infra.attempt.response"]
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
    )
    written = _wire_chat_response(monkeypatch)
    result = await _run_chat_response(uuid4(), owner)
    assert result.success
    assert len(written) == 1


async def test_chat_response_allows_in_scope_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(instructor, "instructional", 2),
        ["app.infra.attempt.response"],
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
    )
    written = _wire_chat_response(monkeypatch)
    result = await _run_chat_response(uuid4(), instructor)
    assert result.success
    assert len(written) == 1


# ── R1c: chat_voice (chat-keyed open-conversation) ────────────────────────────


def _wire_chat_voice(monkeypatch, owner_chat_id):
    import app.infra.websocket.attempt.chat.voice as mod
    from app.tools.entries.attempt_conversations.types import (
        CreateAttemptConversationsResponse,
    )

    opened: list[UUID] = []

    class _GroupResult:
        group_id = uuid4()

    async def fake_group(*a, **k):
        return _GroupResult()

    async def fake_get_chats(conn, ids, redis, **k):
        from app.tools.entries.attempt_chat.types import GetAttemptChatResponse

        return [GetAttemptChatResponse.model_construct(
            chat_id=owner_chat_id, attempt_id=uuid4(), profile_id=uuid4(),
        )]

    async def fake_create(conn, redis, *, chat_id, **kwargs):
        opened.append(chat_id)
        return CreateAttemptConversationsResponse.model_construct(id=uuid4())

    monkeypatch.setattr(mod, "group_attempt_impl", fake_group)
    monkeypatch.setattr(mod, "get_attempt_chats", fake_get_chats)
    monkeypatch.setattr(mod, "create_attempt_conversations", fake_create)
    # The voice impl pulls pool/redis from globals — route to fakes so the gate
    # + conversation create never touch a real DB.
    monkeypatch.setattr(mod, "get_pool", lambda: _FakePool())
    monkeypatch.setattr(mod, "get_redis_client", lambda: object())
    return opened


async def _run_chat_voice(chat_id, actor_id):
    from app.infra.websocket.attempt.chat.voice import (
        attempt_chat_voice_internal_impl,
    )

    return await attempt_chat_voice_internal_impl(
        {
            "chat_id": str(chat_id),
            "profile_id": str(actor_id),
            "session_id": str(uuid4()),
        },
        audit=False,
    )


async def test_chat_voice_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    chat_id = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(attacker, "member", 1),
        ["app.infra.websocket.attempt.chat.voice"],
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
    )
    opened = _wire_chat_voice(monkeypatch, chat_id)
    with pytest.raises(HTTPException) as exc:
        await _run_chat_voice(chat_id, attacker)
    assert exc.value.status_code == 403
    assert opened == []


async def test_chat_voice_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    chat_id = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(instructor, "instructional", 2),
        ["app.infra.websocket.attempt.chat.voice"],
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
    )
    opened = _wire_chat_voice(monkeypatch, chat_id)
    with pytest.raises(HTTPException) as exc:
        await _run_chat_voice(chat_id, instructor)
    assert exc.value.status_code == 403
    assert opened == []


async def test_chat_voice_allows_owner(monkeypatch):
    owner = uuid4()
    chat_id = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(owner, "member", 1),
        ["app.infra.websocket.attempt.chat.voice"],
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
    )
    opened = _wire_chat_voice(monkeypatch, chat_id)
    result = await _run_chat_voice(chat_id, owner)
    assert result.conversation_id
    assert opened == [chat_id]


# ── R1d: chat_audio (message-keyed audio attach) ──────────────────────────────


def _wire_chat_audio(monkeypatch):
    import app.infra.attempt.chat_audio as mod
    from app.tools.entries.attempt_audio.types import CreateAttemptAudioResponse

    written: list[UUID] = []

    async def fake_create(conn, redis, *, message_id, **kwargs):
        written.append(message_id)
        return CreateAttemptAudioResponse.model_construct(id=uuid4())

    async def fake_invalidate(*a, **k):
        return None

    monkeypatch.setattr(mod, "create_attempt_audio", fake_create)
    monkeypatch.setattr(mod, "invalidate_tags", fake_invalidate)
    return written


async def _run_chat_audio(message_id, actor_id):
    from app.infra.attempt.chat_audio import attempt_chat_audio_internal_impl

    return await attempt_chat_audio_internal_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        message_id=message_id, audios_id=uuid4(),
    )


async def test_chat_audio_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    message_id = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(attacker, "member", 1), ["app.infra.attempt.chat_audio"]
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=True,
        message=_message(message_id, uuid4()),
    )
    written = _wire_chat_audio(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_chat_audio(message_id, attacker)
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_audio_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    message_id = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(instructor, "instructional", 2),
        ["app.infra.attempt.chat_audio"],
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
        message=_message(message_id, uuid4()),
    )
    written = _wire_chat_audio(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_chat_audio(message_id, instructor)
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_audio_fails_closed_on_unresolvable_message(monkeypatch):
    """A message_id that resolves to no chat → no owner → DENIED (fail-closed)."""
    actor = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(actor, "instructional", 2),
        ["app.infra.attempt.chat_audio"],
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=uuid4(), department_in_scope=True,
        message=None,  # message not found
    )
    written = _wire_chat_audio(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _run_chat_audio(uuid4(), actor)
    assert exc.value.status_code == 403
    assert written == []


async def test_chat_audio_allows_owner(monkeypatch):
    owner = uuid4()
    message_id = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(owner, "member", 1), ["app.infra.attempt.chat_audio"]
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
        message=_message(message_id, uuid4()),
    )
    written = _wire_chat_audio(monkeypatch)
    result = await _run_chat_audio(message_id, owner)
    assert result.success
    assert written == [message_id]


async def test_chat_audio_allows_superadmin_global(monkeypatch):
    super_id, owner = uuid4(), uuid4()
    message_id = uuid4()
    _wire_resolve_profile_for(
        monkeypatch, _profile(super_id, "superadmin", 4), ["app.infra.attempt.chat_audio"]
    )
    _wire_owner_resolution(
        monkeypatch, owner_profile_id=owner, department_in_scope=False,
        message=_message(message_id, uuid4()),
    )
    written = _wire_chat_audio(monkeypatch)
    result = await _run_chat_audio(message_id, super_id)
    assert result.success
    assert written == [message_id]
