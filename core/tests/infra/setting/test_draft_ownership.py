"""Integration check: the draft-write ownership guard wired into the real
setting-draft impl actually denies a foreign-owned draft_id *before* any write.

Mirrors the report S-A exploit: a caller with the ``setting:draft`` permission
supplies another user's ``draft_id`` and tries to clobber it. The guard must
403 and ``create_setting_draft`` must never run.
"""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.setting.draft import patch_setting_draft_impl
from app.infra.setting.types import PatchSettingDraftApiRequest

pytestmark = pytest.mark.asyncio

_CALLER_SESSION = uuid4()
_OWNER_SESSION = uuid4()  # a *different* user's session
_VICTIM_DRAFT_ID = uuid4()


@dataclass
class _Profile:
    profiles_id = uuid4()
    name = "Attacker"
    role = "admin"
    role_name = "Admin"
    role_description = ""
    role_artifacts: list = None
    primary_email = "a@a.com"
    emails: list = None
    primary_department_id = None
    department_ids: list = None
    settings_id = None
    request_limit = None
    request_limit_interval = None
    is_active = True
    session_id = _CALLER_SESSION
    role_level = 1  # NOT super-admin
    role_permissions: list = None


@dataclass
class _OwnedDraft:
    id = _VICTIM_DRAFT_ID
    session_id = _OWNER_SESSION  # owned by someone else
    profile_ids: list = None


class _Conn:
    async def execute(self, *a, **kw):
        pass

    async def fetch(self, *a, **kw):
        return []

    async def fetchrow(self, *a, **kw):
        return None

    def transaction(self):
        return self._Tx()

    class _Tx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass


class _Pool:
    class _ctx:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *a):
            pass

    def acquire(self):
        return self._ctx()


def _patch_common(monkeypatch):
    async def fake_resolve(*a, **kw):
        return _Profile()

    async def fake_resolve_values(*a, **kw):
        return []

    async def fake_get_drafts(conn, ids, redis, active=True, *, bypass_cache=False):
        return [_OwnedDraft()]

    monkeypatch.setattr(
        "app.infra.setting.draft.resolve_profile_identity_context", fake_resolve
    )
    monkeypatch.setattr(
        "app.infra.setting.draft._resolve_creatable_values", fake_resolve_values
    )
    monkeypatch.setattr(
        "app.infra.setting.draft.compute_can_draft", lambda **kw: True
    )
    monkeypatch.setattr(
        "app.infra.setting.draft.get_setting_drafts", fake_get_drafts
    )


class TestWriteOwnershipDeny:
    async def test_foreign_draft_id_denied_and_not_written(self, monkeypatch):
        _patch_common(monkeypatch)

        write_calls = []

        async def fake_create(*a, **kw):
            write_calls.append(kw.get("id"))
            raise AssertionError("create_setting_draft must not run on deny")

        monkeypatch.setattr(
            "app.infra.setting.draft.create_setting_draft", fake_create
        )

        with pytest.raises(HTTPException) as exc:
            await patch_setting_draft_impl(
                _Pool(),
                object(),
                profile_id=uuid4(),
                session_id=_CALLER_SESSION,
                request=PatchSettingDraftApiRequest(draft_id=_VICTIM_DRAFT_ID),
            )

        assert exc.value.status_code == 403
        assert write_calls == []  # no row mutated
