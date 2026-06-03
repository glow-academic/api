"""Authorization (IDOR) tests for attempt media download impls — issue #148.

The attempt file/audio/image/text download + preview impls gate only on the
coarse global ``has_permission(role, "attempt", "<op>")`` and then fetch the
blob by caller-supplied id with no ownership/role scope. Any holder of the
download permission (members/guests hold it for their own media) could fetch
ANY student's file by id.

These tests pin the fix: each impl now resolves the blob -> its owning
``uploads_entry`` -> session owner profile, then runs ``check_attempt_access``
(owner OR strictly-higher role), mirroring ``get_attempt_internal``.

Strategy: the impls compose black-box tools (resolve_profile_identity_context,
search_*, get_upload, get_sessions). We monkeypatch those composed tools so the
test is deterministic and DB-free, build the actors as real
``ProfileIdentityContext`` objects, and let the real ``check_attempt_access``
decide. A real temp file is placed on disk so that — absent the access check —
the impl would happily return the bytes (the IDOR). The blocked tests therefore
FAIL pre-fix (metadata returned) and PASS post-fix (403); the allowed tests
pass both.

Both directions are covered for ``file_download`` and ``audio_download`` (the
two impls explicitly required by the issue). The other three impls
(``image_download``, ``file_preview``, ``text_download``) call the identical
``enforce_attempt_media_access`` helper, exercised directly here too.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


# ── Actors ──────────────────────────────────────────────────────────────────


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
        # Both download permissions, so has_permission always passes and we are
        # purely exercising the per-resource access gate.
        role_permissions=[
            ("attempt", "file_download"),
            ("attempt", "audio_download"),
            ("attempt", "image_download"),
            ("attempt", "text_download"),
            ("attempt", "file_preview"),
        ],
    )


# ── Fakes for composed black-box tools ───────────────────────────────────────


def _upload_obj(upload_id: UUID, session_id: UUID, file_path: str):
    from app.tools.entries.uploads.types import GetUploadResponse

    return GetUploadResponse(
        id=upload_id,
        session_id=session_id,
        file_path=file_path,
        mime_type="application/pdf",
        size=3,
        created_at=datetime.now(UTC),
        active=True,
        mcp=False,
        generated=False,
    )


def _session_obj(session_id: UUID, owner_profile_id: UUID):
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
    """Pool whose .acquire() yields a dummy connection (the composed tools that
    actually touch the conn are all monkeypatched, so the conn is inert)."""

    def acquire(self):
        return _FakeConn()


def _wire_owner(monkeypatch, *, upload_id: UUID, session_id: UUID, owner_profile_id: UUID):
    """Patch the helper's late-imported owner-resolution tools so the upload
    resolves to ``owner_profile_id`` via session."""
    import app.tools.entries.sessions.get as sessions_get
    import app.tools.entries.uploads.get as uploads_get

    async def fake_get_upload(conn, uid, redis, *, bypass_cache=False):
        assert uid == upload_id
        return _upload_obj(upload_id, session_id, "owned.pdf")

    async def fake_get_sessions(conn, ids, redis, *a, **k):
        assert ids == [session_id]
        return [_session_obj(session_id, owner_profile_id)]

    monkeypatch.setattr(uploads_get, "get_upload", fake_get_upload)
    monkeypatch.setattr(sessions_get, "get_sessions", fake_get_sessions)


def _real_disk_file(monkeypatch, module, folder_attr: str, filename: str = "owned.pdf"):
    """Point the impl's UPLOAD/AUDIO folder at a real temp dir holding the file,
    so absent the access check the impl would return the bytes (the IDOR)."""
    import tempfile

    d = tempfile.mkdtemp()
    with open(os.path.join(d, filename), "wb") as fh:
        fh.write(b"PDF")
    monkeypatch.setattr(module, folder_attr, d)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# file_download
# ─────────────────────────────────────────────────────────────────────────────


def _wire_file_download(monkeypatch, *, actor, upload_id, file_path="owned.pdf"):
    import app.infra.attempt.file_download as mod
    from app.tools.entries.files.types import SearchFileResponse

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_search_files(conn, redis, *, files_ids=None, limit=1, **k):
        return [
            SearchFileResponse(
                file_id=files_ids[0],
                files_id=files_ids[0],
                upload_id=upload_id,
                file_path=file_path,
                mime_type="application/pdf",
                size=3,
                created_at=datetime.now(UTC),
            )
        ]

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "search_files", fake_search_files)
    _real_disk_file(monkeypatch, mod, "UPLOAD_FOLDER", file_path)
    return mod


async def test_file_download_blocks_peer_member(monkeypatch):
    """A member who is NOT the owner and is not higher-role is denied (403)."""
    from app.infra.attempt.file_download import file_download_attempt_impl

    attacker_id, owner_id = uuid4(), uuid4()
    upload_id, session_id, file_id = uuid4(), uuid4(), uuid4()

    actor = _profile(attacker_id, "member", role_level=1)
    _wire_file_download(monkeypatch, actor=actor, upload_id=upload_id)
    _wire_owner(monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id)

    with pytest.raises(HTTPException) as ei:
        await file_download_attempt_impl(
            _FakePool(), object(), profile_id=attacker_id, file_id=file_id
        )
    assert ei.value.status_code == 403


async def test_file_download_allows_owner(monkeypatch):
    """The session owner downloads their own file — works."""
    from app.infra.attempt.file_download import file_download_attempt_impl

    owner_id = uuid4()
    upload_id, session_id, file_id = uuid4(), uuid4(), uuid4()

    actor = _profile(owner_id, "member", role_level=1)
    _wire_file_download(monkeypatch, actor=actor, upload_id=upload_id)
    _wire_owner(monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id)

    result = await file_download_attempt_impl(
        _FakePool(), object(), profile_id=owner_id, file_id=file_id
    )
    assert result.upload_id == upload_id
    assert os.path.exists(result.file_path)


async def test_file_download_allows_higher_role(monkeypatch):
    """A strictly-higher role (instructional) downloads a student's file — works."""
    from app.infra.attempt.file_download import file_download_attempt_impl

    instructor_id, owner_id = uuid4(), uuid4()
    upload_id, session_id, file_id = uuid4(), uuid4(), uuid4()

    actor = _profile(instructor_id, "instructional", role_level=2)
    _wire_file_download(monkeypatch, actor=actor, upload_id=upload_id)
    _wire_owner(monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id)

    result = await file_download_attempt_impl(
        _FakePool(), object(), profile_id=instructor_id, file_id=file_id
    )
    assert result.upload_id == upload_id


# ─────────────────────────────────────────────────────────────────────────────
# audio_download
# ─────────────────────────────────────────────────────────────────────────────


def _wire_audio_download(monkeypatch, *, actor, upload_id, session_id, file_path="owned.pdf"):
    import app.infra.attempt.audio_download as mod
    from app.tools.entries.audio_uploads.types import GetAudioUploadResponse

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_search_audio_uploads(conn, redis, *, audio_ids=None, limit=1, **k):
        return [
            GetAudioUploadResponse(
                id=uuid4(),
                audio_id=audio_ids[0],
                upload_id=upload_id,
                session_id=session_id,
                created_at=datetime.now(UTC),
                active=True,
                mcp=False,
                generated=False,
            )
        ]

    async def fake_get_upload(conn, uid, redis, *, bypass_cache=False):
        # Used by the audio impl itself to resolve the junction's upload row.
        return _upload_obj(upload_id, session_id, file_path)

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "search_audio_uploads", fake_search_audio_uploads)
    monkeypatch.setattr(mod, "get_upload", fake_get_upload)
    _real_disk_file(monkeypatch, mod, "AUDIO_FOLDER", file_path)
    return mod


async def test_audio_download_blocks_peer_member(monkeypatch):
    """A non-owner member is denied another student's recording (403)."""
    from app.infra.attempt.audio_download import audio_download_attempt_impl

    attacker_id, owner_id = uuid4(), uuid4()
    upload_id, session_id, audio_id = uuid4(), uuid4(), uuid4()

    actor = _profile(attacker_id, "member", role_level=1)
    _wire_audio_download(monkeypatch, actor=actor, upload_id=upload_id, session_id=session_id)
    _wire_owner(monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id)

    with pytest.raises(HTTPException) as ei:
        await audio_download_attempt_impl(
            _FakePool(), object(), profile_id=attacker_id, audio_id=audio_id
        )
    assert ei.value.status_code == 403


async def test_audio_download_allows_owner(monkeypatch):
    """The session owner downloads their own recording — works."""
    from app.infra.attempt.audio_download import audio_download_attempt_impl

    owner_id = uuid4()
    upload_id, session_id, audio_id = uuid4(), uuid4(), uuid4()

    actor = _profile(owner_id, "member", role_level=1)
    _wire_audio_download(monkeypatch, actor=actor, upload_id=upload_id, session_id=session_id)
    _wire_owner(monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id)

    result = await audio_download_attempt_impl(
        _FakePool(), object(), profile_id=owner_id, audio_id=audio_id
    )
    assert result.upload_id == upload_id
    assert os.path.exists(result.file_path)


async def test_audio_download_allows_higher_role(monkeypatch):
    """A strictly-higher role downloads a student's recording — works."""
    from app.infra.attempt.audio_download import audio_download_attempt_impl

    instructor_id, owner_id = uuid4(), uuid4()
    upload_id, session_id, audio_id = uuid4(), uuid4(), uuid4()

    actor = _profile(instructor_id, "instructional", role_level=2)
    _wire_audio_download(monkeypatch, actor=actor, upload_id=upload_id, session_id=session_id)
    _wire_owner(monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id)

    result = await audio_download_attempt_impl(
        _FakePool(), object(), profile_id=instructor_id, audio_id=audio_id
    )
    assert result.upload_id == upload_id


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper — direct both-direction coverage (covers image/text/preview too)
# ─────────────────────────────────────────────────────────────────────────────


async def test_enforce_helper_blocks_non_owner_member(monkeypatch):
    from app.infra.attempt.permissions import enforce_attempt_media_access

    attacker_id, owner_id = uuid4(), uuid4()
    upload_id, session_id = uuid4(), uuid4()
    _wire_owner(monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id)

    with pytest.raises(HTTPException) as ei:
        await enforce_attempt_media_access(
            _FakePool(), object(), upload_id=upload_id,
            requester=_profile(attacker_id, "member", role_level=1),
        )
    assert ei.value.status_code == 403


async def test_enforce_helper_allows_owner(monkeypatch):
    from app.infra.attempt.permissions import enforce_attempt_media_access

    owner_id = uuid4()
    upload_id, session_id = uuid4(), uuid4()
    _wire_owner(monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id)

    # Should not raise.
    await enforce_attempt_media_access(
        _FakePool(), object(), upload_id=upload_id,
        requester=_profile(owner_id, "member", role_level=1),
    )


async def test_enforce_helper_allows_higher_role(monkeypatch):
    from app.infra.attempt.permissions import enforce_attempt_media_access

    instructor_id, owner_id = uuid4(), uuid4()
    upload_id, session_id = uuid4(), uuid4()
    _wire_owner(monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner_id)

    await enforce_attempt_media_access(
        _FakePool(), object(), upload_id=upload_id,
        requester=_profile(instructor_id, "instructional", role_level=2),
    )


async def test_enforce_helper_denies_missing_upload_linkage(monkeypatch):
    """Fail-closed: an upload id that resolves to no row is denied."""
    import app.tools.entries.uploads.get as uploads_get
    from app.infra.attempt.permissions import enforce_attempt_media_access

    async def fake_get_upload(conn, uid, redis, *, bypass_cache=False):
        return None

    monkeypatch.setattr(uploads_get, "get_upload", fake_get_upload)

    with pytest.raises(HTTPException) as ei:
        await enforce_attempt_media_access(
            _FakePool(), object(), upload_id=uuid4(),
            requester=_profile(uuid4(), "member", role_level=1),
        )
    assert ei.value.status_code == 403
