"""SEC2 — provider call_download is scoped to the call's owner.

Provider call receipts can carry sensitive create/update arguments. The
download must not be reachable for an arbitrary ``call_id`` just because
the caller holds the role-level ``provider:call_download`` permission —
that is an unscoped IDOR. ``call_download_provider_impl`` is the shared
choke point for the HTTP route + WS handler, so the ownership gate lives
here.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.profile_identity_context import ProfileIdentityContext

pytestmark = pytest.mark.asyncio

MODULE = "app.infra.provider.call_download"
# Ownership resolution now lives in the shared helper module (R2 class-fix);
# the SEC2 exemplar delegates to it, so session lookups patch there.
OWNER_MODULE = "app.infra.upload_owner"


def _profile(profiles_id, *, role_permissions):
    return ProfileIdentityContext(
        profiles_id=profiles_id,
        name="Admin",
        role="admin",
        role_name="Administrator",
        role_description="",
        role_artifacts=[],
        primary_email="a@example.com",
        emails=["a@example.com"],
        primary_department_id=uuid4(),
        department_ids=[uuid4()],
        settings_id=uuid4(),
        request_limit=100,
        request_limit_interval=None,
        is_active=True,
        role_level=1,
        role_permissions=role_permissions,
    )


class _Pool:
    """Async-context-manager pool whose acquire() yields a dummy conn."""

    class _Conn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    def acquire(self):
        return self._Conn()


class _Junction:
    def __init__(self, session_id):
        self.session_id = session_id
        self.upload_id = uuid4()


class _Session:
    def __init__(self, sid):
        self.id = sid


async def test_rejects_unprivileged_caller(monkeypatch):
    """No provider:call_download permission → 403 before any lookup."""
    from app.infra.provider.call_download import call_download_provider_impl

    profile = _profile(uuid4(), role_permissions=[("persona", "update")])

    async def mock_resolve(pool, pid, redis, **kw):
        return profile

    async def mock_search_call_uploads(*a, **k):
        raise AssertionError("must not query uploads before the auth gate")

    monkeypatch.setattr(f"{MODULE}.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr(f"{MODULE}.search_call_uploads", mock_search_call_uploads)

    with pytest.raises(HTTPException) as exc:
        await call_download_provider_impl(
            _Pool(), None, profile_id=uuid4(), call_id=uuid4()
        )
    assert exc.value.status_code == 403


async def test_rejects_cross_owner_call_id(monkeypatch):
    """The IDOR: caller holds the permission but did NOT create the call.

    The call's creating session is NOT among the caller's sessions, so the
    download is refused (404) — no plaintext receipt for a foreign call_id.
    """
    from app.infra.provider.call_download import call_download_provider_impl

    caller_profiles_id = uuid4()
    profile = _profile(
        caller_profiles_id, role_permissions=[("provider", "call_download")]
    )
    foreign_session = uuid4()

    async def mock_resolve(pool, pid, redis, **kw):
        return profile

    async def mock_search_call_uploads(conn, redis, call_ids=None, limit=1):
        return [_Junction(foreign_session)]

    async def mock_search_sessions(conn, redis, profile_ids=None, **kw):
        # Caller owns OTHER sessions, none of them the call's session.
        assert profile_ids == [caller_profiles_id]
        return [_Session(uuid4()), _Session(uuid4())]

    async def mock_get_upload(*a, **k):
        raise AssertionError("must not resolve the upload for a foreign call")

    monkeypatch.setattr(f"{MODULE}.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr(f"{MODULE}.search_call_uploads", mock_search_call_uploads)
    monkeypatch.setattr(f"{OWNER_MODULE}.search_sessions", mock_search_sessions)
    monkeypatch.setattr(f"{MODULE}.get_upload", mock_get_upload)

    with pytest.raises(HTTPException) as exc:
        await call_download_provider_impl(
            _Pool(), None, profile_id=uuid4(), call_id=uuid4()
        )
    assert exc.value.status_code == 404


async def test_allows_owner(monkeypatch, tmp_path):
    """Caller created the call (its session is theirs) → download proceeds."""
    from app.infra.provider import call_download as cd
    from app.infra.provider.call_download import call_download_provider_impl

    caller_profiles_id = uuid4()
    profile = _profile(
        caller_profiles_id, role_permissions=[("provider", "call_download")]
    )
    owned_session = uuid4()
    junction = _Junction(owned_session)

    # A real file on disk so the existence check passes.
    f = tmp_path / "receipt.json"
    f.write_text("{}")

    class _Upload:
        id = junction.upload_id
        file_path = f.name
        mime_type = "application/json"
        size = 2

    async def mock_resolve(pool, pid, redis, **kw):
        return profile

    async def mock_search_call_uploads(conn, redis, call_ids=None, limit=1):
        return [junction]

    async def mock_search_sessions(conn, redis, profile_ids=None, **kw):
        return [_Session(owned_session)]  # the call's session IS the caller's

    async def mock_get_upload(conn, upload_id, redis):
        return _Upload()

    monkeypatch.setattr(f"{MODULE}.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr(f"{MODULE}.search_call_uploads", mock_search_call_uploads)
    monkeypatch.setattr(f"{OWNER_MODULE}.search_sessions", mock_search_sessions)
    monkeypatch.setattr(f"{MODULE}.get_upload", mock_get_upload)
    monkeypatch.setattr(cd, "CALL_FOLDER", str(tmp_path))
    monkeypatch.setattr(cd, "UPLOAD_FOLDER", str(tmp_path))

    result = await call_download_provider_impl(
        _Pool(), None, profile_id=uuid4(), call_id=uuid4()
    )
    assert result.upload_id == junction.upload_id
    assert os.path.basename(result.file_path) == f.name
