"""Authorization tests for the attempt *chat_grade* mutate impl.

``chat_grade_attempt_impl`` (POST /attempt/chat_grade, and the AI-generate
``chat_grade`` operation) had NO authorization beyond authentication: any
authenticated profile could write a grade onto ANY attempt chat by passing its
``chat_id``. The fix mirrors the attempt read/archive gate (``check_attempt_access``,
issue #148): the grader must own the chat's attempt (self-grade) OR hold a
strictly-higher instructional role AND share a department with the attempt owner;
super-admins are global.

Strategy mirrors ``test_archive_idor.py``: the impl composes black-box tools
(``search_attempt_chats``, ``resolve_profile_identity_context``,
``is_profile_in_department_scope``, ``get_rubrics``, ``create_attempt_grade``,
``refresh_attempt_impl``). We monkeypatch those at the
``app.infra.attempt.chat_grade`` namespace and let the real
``check_attempt_access`` decide. A non-owner/non-instructor is denied (403, 0
grades written); the owner, an in-scope instructor, and a super-admin succeed.
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


def _chat(chat_id: UUID, owner_profile_id: UUID | None):
    from app.tools.entries.attempt_chat.types import GetAttemptChatResponse

    # model_construct: bypass validation; set only the fields the impl reads.
    return GetAttemptChatResponse.model_construct(
        chat_id=chat_id,
        profile_id=owner_profile_id,
        rubric_id=None,  # → passed = score > 0, no rubric fetch
        chat_created_at=datetime.now(UTC),
    )


# ── Fakes ──────────────────────────────────────────────────────────────────


class _FakeConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakePool:
    def acquire(self):
        return _FakeConn()


def _wire(monkeypatch, *, actor, chat, department_in_scope=True):
    """Patch the impl's composed tools. Owner resolution + the dept-scope query
    now live in the SHARED authz path (``app.infra.attempt.permissions``) that
    chat_grade routes through, so the chat lookup / dept-scope fakes are patched
    there; the real ``check_attempt_access`` still decides. Records the chat_ids
    actually handed to ``create_attempt_grade``."""
    import app.infra.attempt.chat_grade as mod
    import app.infra.attempt.permissions as perm_mod
    import app.infra.dashboard.visibility as vis_mod
    import app.infra.profile_identity_context as pic_mod
    from app.tools.entries.attempt_grade.types import CreateAttemptGradeResponse

    graded_ids: list[UUID] = []

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_search_chats(conn, redis, **kwargs):
        return ([chat], 1)

    async def fake_dept_scope(pool, caller, owner_profiles_id, *a, **k):
        return department_in_scope

    async def fake_create_grade(conn, redis, *, chat_id, **kwargs):
        graded_ids.append(chat_id)
        return CreateAttemptGradeResponse(id=uuid4())

    async def fake_refresh(*a, **k):
        return None

    monkeypatch.setattr(pic_mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(
        mod, "resolve_profile_identity_context", fake_resolve, raising=False
    )
    # The shared helper imports search_attempt_chats locally — patch at source.
    import app.tools.entries.attempt_chat.search as chat_search_mod
    monkeypatch.setattr(chat_search_mod, "search_attempt_chats", fake_search_chats)
    monkeypatch.setattr(vis_mod, "is_profile_in_department_scope", fake_dept_scope)
    # chat_grade still fetches the chat itself (for rubric / created_at).
    monkeypatch.setattr(mod, "search_attempt_chats", fake_search_chats)
    monkeypatch.setattr(mod, "create_attempt_grade", fake_create_grade)
    monkeypatch.setattr(mod, "refresh_attempt_impl", fake_refresh)
    return graded_ids


async def _run(*, actor_profile_id, chat):
    from app.infra.attempt.chat_grade import chat_grade_attempt_impl

    return await chat_grade_attempt_impl(
        _FakePool(),
        object(),
        profile_id=actor_profile_id,
        session_id=uuid4(),
        chat_id=chat.chat_id,
        score=5,
    )


# ─────────────────────────────────────────────────────────────────────────────


async def test_chat_grade_blocks_peer_member(monkeypatch):
    """A non-owner member grading another student's chat is denied (403)."""
    attacker_id, owner_id = uuid4(), uuid4()
    chat = _chat(uuid4(), owner_id)

    actor = _profile(attacker_id, "member", role_level=1)
    graded_ids = _wire(monkeypatch, actor=actor, chat=chat)

    with pytest.raises(HTTPException) as exc:
        await _run(actor_profile_id=attacker_id, chat=chat)
    assert exc.value.status_code == 403
    assert graded_ids == []  # no grade written


async def test_chat_grade_allows_owner(monkeypatch):
    """The chat owner grades their own chat — works (self-grade)."""
    owner_id = uuid4()
    chat = _chat(uuid4(), owner_id)

    actor = _profile(owner_id, "member", role_level=1)
    graded_ids = _wire(monkeypatch, actor=actor, chat=chat)

    result = await _run(actor_profile_id=owner_id, chat=chat)
    assert result["grade_id"]
    assert graded_ids == [chat.chat_id]


async def test_chat_grade_allows_in_scope_instructor(monkeypatch):
    """A strictly-higher role sharing the owner's department grades — works."""
    instructor_id, owner_id = uuid4(), uuid4()
    chat = _chat(uuid4(), owner_id)

    actor = _profile(instructor_id, "instructional", role_level=2)
    graded_ids = _wire(
        monkeypatch, actor=actor, chat=chat, department_in_scope=True
    )

    result = await _run(actor_profile_id=instructor_id, chat=chat)
    assert result["grade_id"]
    assert graded_ids == [chat.chat_id]


async def test_chat_grade_blocks_cross_department_instructor(monkeypatch):
    """A higher role whose owner is OUTSIDE its department scope is denied."""
    instructor_id, owner_id = uuid4(), uuid4()
    chat = _chat(uuid4(), owner_id)

    actor = _profile(instructor_id, "instructional", role_level=2)
    graded_ids = _wire(
        monkeypatch, actor=actor, chat=chat, department_in_scope=False
    )

    with pytest.raises(HTTPException) as exc:
        await _run(actor_profile_id=instructor_id, chat=chat)
    assert exc.value.status_code == 403
    assert graded_ids == []


async def test_chat_grade_allows_superadmin_global(monkeypatch):
    """A super-admin grades any chat regardless of department (global)."""
    super_id, owner_id = uuid4(), uuid4()
    chat = _chat(uuid4(), owner_id)

    actor = _profile(super_id, "superadmin", role_level=0)
    graded_ids = _wire(
        monkeypatch, actor=actor, chat=chat, department_in_scope=False
    )

    result = await _run(actor_profile_id=super_id, chat=chat)
    assert result["grade_id"]
    assert graded_ids == [chat.chat_id]


async def test_chat_grade_rejects_positive_score_against_zero_total_rubric(monkeypatch):
    """F4: a resolved rubric bounds the score to its max, INCLUDING a 0-total
    rubric — a positive score against a 0-max rubric is rejected. The old
    ``total_points > 0`` guard skipped the check at 0, silently storing a
    score > 0 against a 0-max rubric (invalid: you can't score 5/0)."""
    import app.infra.attempt.chat_grade as mod
    from app.tools.entries.attempt_chat.types import GetAttemptChatResponse
    from app.tools.resources.rubrics.types import GetRubricResponse

    owner_id, rubric_id = uuid4(), uuid4()
    chat = GetAttemptChatResponse.model_construct(
        chat_id=uuid4(), profile_id=owner_id, rubric_id=rubric_id,
        chat_created_at=datetime.now(UTC),
    )
    actor = _profile(owner_id, "member", role_level=1)  # owner → passes authz
    graded_ids = _wire(monkeypatch, actor=actor, chat=chat)

    async def fake_get_rubrics(conn, ids, redis, *a, **k):
        return [GetRubricResponse.model_construct(
            id=rubric_id, total_points=0, pass_points=0,
        )]
    monkeypatch.setattr(mod, "get_rubrics", fake_get_rubrics)

    with pytest.raises(ValueError) as exc:
        await _run(actor_profile_id=owner_id, chat=chat)  # _run grades score=5
    assert "exceeds maximum of 0" in str(exc.value)
    assert graded_ids == []  # no grade written against the 0-max rubric


async def test_chat_grade_fails_closed_on_unhydrated_owner(monkeypatch):
    """A chat with no resolvable owner (profile_id None) is denied — fail closed."""
    actor_id = uuid4()
    chat = _chat(uuid4(), None)

    actor = _profile(actor_id, "instructional", role_level=2)
    graded_ids = _wire(monkeypatch, actor=actor, chat=chat)

    with pytest.raises(HTTPException) as exc:
        await _run(actor_profile_id=actor_id, chat=chat)
    assert exc.value.status_code == 403
    assert graded_ids == []
