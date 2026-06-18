"""Authorization (IDOR) test for /attempt/audio_upload PROMOTION (M2).

``audio_upload_attempt_impl`` accepts a caller-supplied ``upload_id`` to PROMOTE
an existing upload (e.g. a realtime capture) into a NEW ``audios_entry`` under
the CALLER's session. The media layer only existence-checks the id and disclaims
auth ("authorization lives at the artifact boundary"), so without a gate at the
attempt boundary a caller holding another user's ``upload_id`` could clone that
user's audio blob.

The fix reuses the SAME ``enforce_attempt_media_access`` gate that protects
attempt media downloads (resolve upload -> owning session -> owner profile ->
owner-or-strictly-higher-role + department scope; authored/profile-less content
is shared). These tests pin: a foreign-owned upload is denied (403, and
``media_upload_impl`` is never reached); the owner / higher-role / authored
cases pass the gate and proceed to promotion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


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
        role_permissions=[("attempt", "audio_upload")],
    )


def _upload_obj(upload_id: UUID, session_id: UUID):
    from app.tools.entries.uploads.types import GetUploadResponse

    return GetUploadResponse(
        id=upload_id,
        session_id=session_id,
        file_path="capture.webm",
        mime_type="audio/webm",
        size=3,
        created_at=datetime.now(UTC),
        active=True,
        mcp=False,
        generated=False,
    )


def _session_obj(session_id: UUID, owner_profile_id: UUID | None):
    from app.tools.entries.sessions.types import GetSessionResponse

    return GetSessionResponse(
        id=session_id,
        profile_id=owner_profile_id,
        created_at=datetime.now(UTC),
        active=True,
        mcp=False,
    )


class _FakeConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakePool:
    def acquire(self):
        return _FakeConn()


def _wire(monkeypatch, *, actor, upload_id, session_id, owner_profile_id,
          department_in_scope=True, sessions_empty=False):
    """Patch the boundary impl's resolve + the gate's late-imported owner
    resolution, and stub media_upload_impl so the ALLOW path doesn't touch disk.
    Returns a dict tracking whether media_upload_impl was reached."""
    import app.infra.attempt.audio_upload as mod
    import app.infra.dashboard.visibility as visibility
    import app.tools.entries.sessions.get as sessions_get
    import app.tools.entries.uploads.get as uploads_get

    reached = {"media_upload": False}

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_get_upload(conn, uid, redis, *, bypass_cache=False):
        return _upload_obj(upload_id, session_id)

    async def fake_get_sessions(conn, ids, redis, *a, **k):
        return [] if sessions_empty else [_session_obj(session_id, owner_profile_id)]

    async def fake_in_scope(pool, caller, owner_profiles_id):
        return department_in_scope

    async def fake_media_upload(pool, redis, **kwargs):
        reached["media_upload"] = True
        # Shape mirrors media_upload_impl's return — the boundary maps
        # entry_id/resource_id/junction_id/upload_id into its API response.
        from types import SimpleNamespace

        return SimpleNamespace(
            entry_id=uuid4(),
            resource_id=uuid4(),
            junction_id=uuid4(),
            upload_id=upload_id,
        )

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "media_upload_impl", fake_media_upload)
    monkeypatch.setattr(uploads_get, "get_upload", fake_get_upload)
    monkeypatch.setattr(sessions_get, "get_sessions", fake_get_sessions)
    monkeypatch.setattr(visibility, "is_profile_in_department_scope", fake_in_scope)
    return mod, reached


async def test_promote_blocks_foreign_owned_upload(monkeypatch):
    """A member promoting another user's upload_id → 403, never reaching the
    media layer (no clone)."""
    from app.infra.attempt.audio_upload import audio_upload_attempt_impl

    attacker_id, owner_id = uuid4(), uuid4()
    upload_id, session_id = uuid4(), uuid4()
    mod, reached = _wire(
        monkeypatch, actor=_profile(attacker_id, "member", 1),
        upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id,
    )

    with pytest.raises(HTTPException) as ei:
        await audio_upload_attempt_impl(
            _FakePool(), object(), profile_id=attacker_id, upload_id=upload_id,
        )
    assert ei.value.status_code == 403
    assert reached["media_upload"] is False  # gate fired BEFORE the clone


async def test_promote_allows_owner(monkeypatch):
    """The upload's owner promoting their own capture → reaches the media layer."""
    from app.infra.attempt.audio_upload import audio_upload_attempt_impl

    owner_id = uuid4()
    upload_id, session_id = uuid4(), uuid4()
    mod, reached = _wire(
        monkeypatch, actor=_profile(owner_id, "member", 1),
        upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id,
    )

    result = await audio_upload_attempt_impl(
        _FakePool(), object(), profile_id=owner_id, upload_id=upload_id,
    )
    assert result.upload_id == upload_id
    assert reached["media_upload"] is True


async def test_promote_blocks_cross_department_higher_role(monkeypatch):
    """A higher-role caller in a DIFFERENT department → 403 (mirrors media
    download #152/#148)."""
    from app.infra.attempt.audio_upload import audio_upload_attempt_impl

    instructor_id, owner_id = uuid4(), uuid4()
    upload_id, session_id = uuid4(), uuid4()
    mod, reached = _wire(
        monkeypatch, actor=_profile(instructor_id, "instructional", 2),
        upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id,
        department_in_scope=False,
    )

    with pytest.raises(HTTPException) as ei:
        await audio_upload_attempt_impl(
            _FakePool(), object(), profile_id=instructor_id, upload_id=upload_id,
        )
    assert ei.value.status_code == 403
    assert reached["media_upload"] is False


async def test_promote_allows_authored_profileless_upload(monkeypatch):
    """An upload whose owning session has no profile owner (authored/seed) is
    shared content — promotion is allowed."""
    from app.infra.attempt.audio_upload import audio_upload_attempt_impl

    requester_id = uuid4()
    upload_id, session_id = uuid4(), uuid4()
    mod, reached = _wire(
        monkeypatch, actor=_profile(requester_id, "member", 1),
        upload_id=upload_id, session_id=session_id, owner_profile_id=None,
        sessions_empty=True,
    )

    result = await audio_upload_attempt_impl(
        _FakePool(), object(), profile_id=requester_id, upload_id=upload_id,
    )
    assert result.upload_id == upload_id
    assert reached["media_upload"] is True
