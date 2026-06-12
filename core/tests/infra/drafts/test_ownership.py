"""Allow/deny matrix for the shared draft-write ownership guard.

``enforce_draft_owner`` is the single chokepoint every ``patch_*_draft_impl``
upsert now passes through, so the class is covered by exercising it directly:

  * brand-new id (None or no existing row) → ALLOW (don't break first-write)
  * existing draft owned by caller's session → ALLOW
  * existing draft owned by caller's profile (profiles_id) → ALLOW
  * existing draft owned by ANOTHER session+profile → DENY 403, no getter
    leak, and crucially the guard raises *before* any write
  * super-admin (role_level == 0) → ALLOW regardless of owner
  * a getter that omits the ``active`` kwarg (chat/invocation) → called
    without it (no TypeError)
"""

from dataclasses import dataclass, field
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.drafts.ownership import enforce_draft_owner

pytestmark = pytest.mark.asyncio


@dataclass
class _Draft:
    session_id: object
    profile_ids: list = field(default_factory=list)


class _Conn:
    pass


def _getter_returning(rows, *, record_calls=None, accepts_active=True):
    """Build a fake ``get_*_drafts`` recording its call kwargs."""

    if accepts_active:

        async def getter(conn, ids, redis, active=True, *, bypass_cache=False):
            if record_calls is not None:
                record_calls.append({"ids": ids, "active": active, "bypass_cache": bypass_cache})
            return list(rows)

    else:

        async def getter(conn, ids, redis, *, bypass_cache=False):
            if record_calls is not None:
                record_calls.append({"ids": ids, "bypass_cache": bypass_cache})
            return list(rows)

    return getter


class TestAllow:
    async def test_none_draft_id_is_allowed_without_query(self):
        calls = []
        await enforce_draft_owner(
            _Conn(), object(),
            draft_id=None,
            getter=_getter_returning([], record_calls=calls),
            caller_session_id=uuid4(),
            caller_profile_id=uuid4(),
            role_level=1,
            artifact="setting",
        )
        assert calls == []  # never queried — nothing to clash with

    async def test_no_existing_row_is_allowed(self):
        # First-write / legitimate upsert of the caller's own fresh id.
        await enforce_draft_owner(
            _Conn(), object(),
            draft_id=uuid4(),
            getter=_getter_returning([]),
            caller_session_id=uuid4(),
            caller_profile_id=uuid4(),
            role_level=1,
            artifact="setting",
        )

    async def test_owned_by_caller_session_is_allowed(self):
        sid = uuid4()
        draft = _Draft(session_id=sid, profile_ids=[uuid4()])
        await enforce_draft_owner(
            _Conn(), object(),
            draft_id=uuid4(),
            getter=_getter_returning([draft]),
            caller_session_id=sid,
            caller_profile_id=uuid4(),
            role_level=1,
            artifact="persona",
        )

    async def test_owned_by_caller_profile_is_allowed(self):
        pid = uuid4()
        # Different session, but the caller's profile is on the draft.
        draft = _Draft(session_id=uuid4(), profile_ids=[uuid4(), pid])
        await enforce_draft_owner(
            _Conn(), object(),
            draft_id=uuid4(),
            getter=_getter_returning([draft]),
            caller_session_id=uuid4(),
            caller_profile_id=pid,
            role_level=1,
            artifact="persona",
        )

    async def test_super_admin_bypasses_without_query(self):
        calls = []
        await enforce_draft_owner(
            _Conn(), object(),
            draft_id=uuid4(),
            getter=_getter_returning([_Draft(session_id=uuid4())], record_calls=calls),
            caller_session_id=uuid4(),
            caller_profile_id=uuid4(),
            role_level=0,  # super-admin
            artifact="setting",
        )
        assert calls == []  # short-circuits before any read


class TestDeny:
    async def test_other_owner_denied_403(self):
        # Draft belongs to a different session AND a different profile.
        draft = _Draft(session_id=uuid4(), profile_ids=[uuid4()])
        with pytest.raises(HTTPException) as exc:
            await enforce_draft_owner(
                _Conn(), object(),
                draft_id=uuid4(),
                getter=_getter_returning([draft]),
                caller_session_id=uuid4(),
                caller_profile_id=uuid4(),
                role_level=1,
                artifact="setting",
            )
        assert exc.value.status_code == 403
        assert "setting" in exc.value.detail

    async def test_setting_style_session_only_other_owner_denied(self):
        # Setting drafts carry no profile_ids — session mismatch alone denies.
        draft = _Draft(session_id=uuid4(), profile_ids=[])
        with pytest.raises(HTTPException) as exc:
            await enforce_draft_owner(
                _Conn(), object(),
                draft_id=uuid4(),
                getter=_getter_returning([draft]),
                caller_session_id=uuid4(),
                caller_profile_id=uuid4(),
                role_level=1,
                artifact="setting",
            )
        assert exc.value.status_code == 403


class TestGetterShapes:
    async def test_active_kwarg_passed_when_supported(self):
        calls = []
        await enforce_draft_owner(
            _Conn(), object(),
            draft_id=uuid4(),
            getter=_getter_returning([], record_calls=calls, accepts_active=True),
            caller_session_id=uuid4(),
            caller_profile_id=uuid4(),
            role_level=1,
            artifact="persona",
        )
        assert calls and calls[0]["active"] is None
        assert calls[0]["bypass_cache"] is True

    async def test_getter_without_active_kwarg_is_called_cleanly(self):
        # chat/invocation getters omit ``active``; guard must not pass it.
        calls = []
        await enforce_draft_owner(
            _Conn(), object(),
            draft_id=uuid4(),
            getter=_getter_returning([], record_calls=calls, accepts_active=False),
            caller_session_id=uuid4(),
            caller_profile_id=uuid4(),
            role_level=1,
            artifact="attempt",
        )
        assert calls and "active" not in calls[0]
        assert calls[0]["bypass_cache"] is True
