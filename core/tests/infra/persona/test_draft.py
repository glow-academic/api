"""Tests for persona draft — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.persona.draft import patch_persona_draft_impl
from app.infra.persona.types import PatchPersonaDraftApiRequest

pytestmark = pytest.mark.asyncio

_PROFILE_ID = uuid4()


@dataclass
class _FakeProfile:
    profiles_id = uuid4()
    name = "Test User"
    role = "admin"
    role_name = "Admin"
    role_description = "Administrator"
    role_artifacts = []
    primary_email = "test@test.com"
    emails = ["test@test.com"]
    primary_department_id = None
    department_ids = []
    settings_id = None
    request_limit = None
    request_limit_interval = None
    is_active = True
    session_id = None
    group_id = uuid4()
    role_level = 1
    role_permissions = []


class _FakeConn:
    async def execute(self, *a, **kw):
        pass

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return None

    async def fetchrow(self, *a, **kw):
        return None

    def transaction(self):
        return self._FakeTx()

    class _FakeTx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass


class _FakePool:
    class _ctx:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, *a):
            pass

    def acquire(self):
        return self._ctx()


class TestAuth:
    async def test_raises_401_when_profile_not_found(self, monkeypatch):
        async def fake_resolve(*args, **kw):
            return None

        monkeypatch.setattr(
            "app.infra.persona.draft.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await patch_persona_draft_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
                session_id=_PROFILE_ID,
                request=PatchPersonaDraftApiRequest(),
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.persona.draft.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await patch_persona_draft_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
                session_id=_PROFILE_ID,
                request=PatchPersonaDraftApiRequest(),
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(patch_persona_draft_impl)


# ── Accept/promote-path ownership guard ──────────────────────────────────────
# Closes the last residual of the draft-PATCH write-IDOR class: persona's
# accept/promote branch must enforce_draft_owner exactly like its main upsert
# (and like scenario's accept path). A holder of the draft permission who learns
# another user's draft_id must NOT be able to promote (accept) that draft.

_CALLER_SESSION = uuid4()
_CALLER_PROFILE = uuid4()
_OWNER_SESSION = uuid4()  # a *different* user's session
_OWNER_PROFILE = uuid4()  # a *different* user's profile


@dataclass
class _AckProfile:
    profiles_id = _CALLER_PROFILE
    role_level = 1  # NOT super-admin
    role_permissions: list = None
    department_ids: list = None
    session_id = _CALLER_SESSION


@dataclass
class _AckSuperProfile(_AckProfile):
    role_level = 0  # super-admin → bypass


@dataclass
class _PersonaDraftRow:
    """Shape get_persona_drafts returns on the accept path."""

    id: object
    session_id: object
    profile_ids: list
    # The promote re-write reads these; None is fine for the test create stub.
    name_ids = None
    description_ids = None
    color_ids = None
    icon_ids = None
    instruction_ids = None
    flag_ids = None
    department_ids = None
    parameter_field_ids = None
    example_ids = None
    voice_ids = None


@dataclass
class _PendingEntry:
    artifact_id: object
    status: str = "pending"
    operation: str = "draft"


def _wire_accept(monkeypatch, *, profile, draft_row, target_id, create_calls):
    """Patch the persona accept-path collaborators so only the guard is live."""
    mod = "app.infra.persona.draft"

    async def fake_resolve(*a, **kw):
        return profile

    async def fake_get_soft_call(conn, call_id, redis, *, artifact=None):
        return _PendingEntry(artifact_id=target_id)

    async def fake_get_drafts(conn, ids, redis, active=True, *, bypass_cache=False):
        return [draft_row] if draft_row is not None else []

    async def fake_create(*a, **kw):
        create_calls.append(kw.get("id"))

        @dataclass
        class _Res:
            id: object
        return _Res(id=kw.get("id"))

    async def fake_noop(*a, **kw):
        return None

    monkeypatch.setattr(f"{mod}.resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(f"{mod}.get_soft_call", fake_get_soft_call)
    monkeypatch.setattr(f"{mod}.get_persona_drafts", fake_get_drafts)
    monkeypatch.setattr(f"{mod}.create_persona_draft", fake_create)
    monkeypatch.setattr(f"{mod}.create_soft_call", fake_noop)
    monkeypatch.setattr(f"{mod}.refresh_persona_impl", fake_noop)


async def _run_accept(monkeypatch, *, profile, draft_row):
    target_id = uuid4()
    if draft_row is not None:
        draft_row.id = target_id
    create_calls: list = []
    _wire_accept(
        monkeypatch,
        profile=profile,
        draft_row=draft_row,
        target_id=target_id,
        create_calls=create_calls,
    )
    result = await patch_persona_draft_impl(
        _FakePool(),
        object(),
        profile_id=uuid4(),
        session_id=_CALLER_SESSION,
        accept=True,
        idempotency_key=uuid4(),  # resolves to target_id via get_soft_call stub
    )
    return result, create_calls


class TestAcceptPathOwnership:
    async def test_foreign_owner_accept_denied_403_and_not_promoted(self, monkeypatch):
        foreign = _PersonaDraftRow(
            id=None, session_id=_OWNER_SESSION, profile_ids=[_OWNER_PROFILE]
        )
        with pytest.raises(HTTPException) as exc:
            await _run_accept(monkeypatch, profile=_AckProfile(), draft_row=foreign)
        assert exc.value.status_code == 403

    async def test_owned_by_caller_session_accept_allowed(self, monkeypatch):
        own = _PersonaDraftRow(
            id=None, session_id=_CALLER_SESSION, profile_ids=[_OWNER_PROFILE]
        )
        _result, create_calls = await _run_accept(
            monkeypatch, profile=_AckProfile(), draft_row=own
        )
        assert create_calls, "owner (session match) accept should promote the draft"

    async def test_owned_by_caller_profile_accept_allowed(self, monkeypatch):
        own = _PersonaDraftRow(
            id=None, session_id=_OWNER_SESSION, profile_ids=[_CALLER_PROFILE]
        )
        _result, create_calls = await _run_accept(
            monkeypatch, profile=_AckProfile(), draft_row=own
        )
        assert create_calls, "owner (profile match) accept should promote the draft"

    async def test_super_admin_accept_bypass_allowed(self, monkeypatch):
        foreign = _PersonaDraftRow(
            id=None, session_id=_OWNER_SESSION, profile_ids=[_OWNER_PROFILE]
        )
        _result, create_calls = await _run_accept(
            monkeypatch, profile=_AckSuperProfile(), draft_row=foreign
        )
        assert create_calls, "super-admin should bypass the accept-path guard"
