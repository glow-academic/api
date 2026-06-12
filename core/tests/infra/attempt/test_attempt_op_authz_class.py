"""Class-fix authz tests for the attempt-OPERATION family (M1 sweep).

Report-9 M1: ``stop_attempt_impl`` cancels an in-flight generation purely by a
caller-supplied ``group_id`` with NO ownership check (targeted DoS). The same
owner-mutation gap lived in its siblings that operate on a caller-supplied
attempt-scoped id without scoping to the actor:

  * ``stop``           (group_id → cancel generation)        [M1]
  * ``title``          (group_id → rename attempt group)     [M1 sibling]
  * ``call_download``  (call_id  → download call media)      [media IDOR sibling]
  * ``video_download`` (video_id → download session video)   [media IDOR sibling]

All now route through the SHARED attempt-access gates in
``app.infra.attempt.permissions``:

  * ``enforce_attempt_access_by_group`` (group_id → session → owner) — NEW
  * ``enforce_attempt_media_access``    (upload_id → session → owner) — reused

each funnelling into the same ``check_attempt_access`` + dept-scope gate the
read/complete/archive paths use (#148): owner → allowed; super-admin → global;
strictly-higher role in the owner's department → allowed; else 403 (fail-closed
on unresolved owner). The deny assertions prove NO side effect (no generation
cancelled, no media metadata returned).

DB-free: the composed black-box resolvers (groups/sessions/uploads/videos/calls
+ the dept-scope query + the cancel helpers) are monkeypatched and the REAL gate
decides.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


# ── Actors / fakes ────────────────────────────────────────────────────────────


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
        # Both download caps so has_permission always passes — we exercise the
        # per-resource OWNERSHIP gate, not the coarse role capability.
        role_permissions=[
            ("attempt", "call_download"),
            ("attempt", "video_download"),
        ],
    )


class _FakeConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakePool:
    def acquire(self):
        return _FakeConn()


def _group(group_id: UUID, session_id: UUID | None):
    from app.tools.entries.groups.types import GetGroupResponse

    return GetGroupResponse.model_construct(id=group_id, session_id=session_id)


def _session(session_id: UUID, owner_profile_id: UUID | None):
    from app.tools.entries.sessions.types import GetSessionResponse

    return GetSessionResponse(
        id=session_id,
        profile_id=owner_profile_id,
        created_at=datetime.now(UTC),
        active=True,
        mcp=False,
    )


def _wire_group_owner(
    monkeypatch, *, group_id, session_id, owner_profile_id, department_in_scope=True
):
    """Patch the late-imported group/session resolvers used by
    ``enforce_attempt_access_by_group`` so the group resolves to an owner."""
    import app.infra.dashboard.visibility as vis_mod
    import app.tools.entries.groups.get as groups_get
    import app.tools.entries.sessions.get as sessions_get

    async def fake_get_groups(conn, ids, redis, *a, **k):
        return [_group(group_id, session_id)]

    async def fake_get_sessions(conn, ids, redis, *a, **k):
        return [_session(session_id, owner_profile_id)]

    async def fake_in_scope(pool, caller, owner_profiles_id, *a, **k):
        return department_in_scope

    monkeypatch.setattr(groups_get, "get_groups", fake_get_groups)
    monkeypatch.setattr(sessions_get, "get_sessions", fake_get_sessions)
    monkeypatch.setattr(vis_mod, "is_profile_in_department_scope", fake_in_scope)


# ─────────────────────────────────────────────────────────────────────────────
# enforce_attempt_access_by_group — the shared helper (direct coverage)
# ─────────────────────────────────────────────────────────────────────────────


async def test_group_gate_blocks_peer_member(monkeypatch):
    from app.infra.attempt.permissions import enforce_attempt_access_by_group

    attacker, owner = uuid4(), uuid4()
    group_id, session_id = uuid4(), uuid4()
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id, owner_profile_id=owner
    )
    with pytest.raises(HTTPException) as exc:
        await enforce_attempt_access_by_group(
            _FakePool(), object(), group_id=group_id,
            requester=_profile(attacker, "member", 1),
        )
    assert exc.value.status_code == 403


async def test_group_gate_blocks_cross_department_instructor(monkeypatch):
    from app.infra.attempt.permissions import enforce_attempt_access_by_group

    instructor, owner = uuid4(), uuid4()
    group_id, session_id = uuid4(), uuid4()
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id,
        owner_profile_id=owner, department_in_scope=False,
    )
    with pytest.raises(HTTPException) as exc:
        await enforce_attempt_access_by_group(
            _FakePool(), object(), group_id=group_id,
            requester=_profile(instructor, "instructional", 2),
        )
    assert exc.value.status_code == 403


async def test_group_gate_allows_owner(monkeypatch):
    from app.infra.attempt.permissions import enforce_attempt_access_by_group

    owner = uuid4()
    group_id, session_id = uuid4(), uuid4()
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id,
        owner_profile_id=owner, department_in_scope=False,
    )
    await enforce_attempt_access_by_group(
        _FakePool(), object(), group_id=group_id,
        requester=_profile(owner, "member", 1),
    )


async def test_group_gate_allows_in_scope_instructor(monkeypatch):
    from app.infra.attempt.permissions import enforce_attempt_access_by_group

    instructor, owner = uuid4(), uuid4()
    group_id, session_id = uuid4(), uuid4()
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id,
        owner_profile_id=owner, department_in_scope=True,
    )
    await enforce_attempt_access_by_group(
        _FakePool(), object(), group_id=group_id,
        requester=_profile(instructor, "instructional", 2),
    )


async def test_group_gate_allows_superadmin_global(monkeypatch):
    from app.infra.attempt.permissions import enforce_attempt_access_by_group

    super_id, owner = uuid4(), uuid4()
    group_id, session_id = uuid4(), uuid4()
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id,
        owner_profile_id=owner, department_in_scope=False,
    )
    await enforce_attempt_access_by_group(
        _FakePool(), object(), group_id=group_id,
        requester=_profile(super_id, "superadmin", 4),
    )


async def test_group_gate_fails_closed_on_unresolvable_group(monkeypatch):
    """A group_id resolving to no session/owner → DENIED (fail-closed)."""
    import app.tools.entries.groups.get as groups_get
    from app.infra.attempt.permissions import enforce_attempt_access_by_group

    async def fake_get_groups(conn, ids, redis, *a, **k):
        return []

    monkeypatch.setattr(groups_get, "get_groups", fake_get_groups)
    with pytest.raises(HTTPException) as exc:
        await enforce_attempt_access_by_group(
            _FakePool(), object(), group_id=uuid4(),
            requester=_profile(uuid4(), "instructional", 2),
        )
    assert exc.value.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# stop_attempt_impl (M1) — immediate cancel path
# ─────────────────────────────────────────────────────────────────────────────


def _wire_stop(monkeypatch, actor):
    """Patch resolve_profile + the three cancel helpers; record any cancel."""
    import app.infra.attempt.stop as mod

    cancelled: list[str] = []

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_cancel(gid):
        cancelled.append(str(gid))

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "cancel_active_result", fake_cancel)
    monkeypatch.setattr(mod, "cancel_active_run", fake_cancel)
    monkeypatch.setattr(mod, "cancel_realtime_turn", fake_cancel)
    return cancelled


async def test_stop_blocks_peer_member(monkeypatch):
    from app.infra.attempt.stop import stop_attempt_impl

    attacker, owner = uuid4(), uuid4()
    group_id, session_id = uuid4(), uuid4()
    actor = _profile(attacker, "member", 1)
    cancelled = _wire_stop(monkeypatch, actor)
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id, owner_profile_id=owner
    )
    with pytest.raises(HTTPException) as exc:
        await stop_attempt_impl(
            _FakePool(), object(), profile_id=attacker, group_id=group_id,
        )
    assert exc.value.status_code == 403
    assert cancelled == [], "non-owner stop cancelled a generation (DoS)"


async def test_stop_allows_owner(monkeypatch):
    from app.infra.attempt.stop import stop_attempt_impl

    owner = uuid4()
    group_id, session_id = uuid4(), uuid4()
    actor = _profile(owner, "member", 1)
    cancelled = _wire_stop(monkeypatch, actor)
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id,
        owner_profile_id=owner, department_in_scope=False,
    )
    result = await stop_attempt_impl(
        _FakePool(), object(), profile_id=owner, group_id=group_id,
    )
    assert result.success is True
    assert len(cancelled) == 3  # all three cancel helpers fired for the owner


async def test_stop_allows_superadmin(monkeypatch):
    from app.infra.attempt.stop import stop_attempt_impl

    super_id, owner = uuid4(), uuid4()
    group_id, session_id = uuid4(), uuid4()
    actor = _profile(super_id, "superadmin", 4)
    cancelled = _wire_stop(monkeypatch, actor)
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id,
        owner_profile_id=owner, department_in_scope=False,
    )
    result = await stop_attempt_impl(
        _FakePool(), object(), profile_id=super_id, group_id=group_id,
    )
    assert result.success is True
    assert len(cancelled) == 3


# ─────────────────────────────────────────────────────────────────────────────
# title_attempt_impl (M1 sibling) — group rename
# ─────────────────────────────────────────────────────────────────────────────


def _wire_title(monkeypatch, actor):
    """Patch resolve_profile + the generic title_group_impl (record renames)."""
    import app.infra.attempt.title as mod

    renamed: list[UUID] = []

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_title_group(pool, redis, *, artifact_type, group_id=None, **k):
        renamed.append(group_id)
        from app.infra.group.title import TitleGroupResponse

        return TitleGroupResponse(
            group_id=group_id, group_name_id=uuid4(), title="t", idempotency_key=None,
        )

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "title_group_impl", fake_title_group)
    return renamed


async def test_title_blocks_peer_member(monkeypatch):
    from app.infra.attempt.title import title_attempt_impl

    attacker, owner = uuid4(), uuid4()
    group_id, session_id = uuid4(), uuid4()
    renamed = _wire_title(monkeypatch, _profile(attacker, "member", 1))
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id, owner_profile_id=owner
    )
    with pytest.raises(HTTPException) as exc:
        await title_attempt_impl(
            _FakePool(), object(), profile_id=attacker, session_id=session_id,
            group_id=group_id, title="hijacked",
        )
    assert exc.value.status_code == 403
    assert renamed == [], "non-owner renamed another user's attempt group"


async def test_title_allows_owner(monkeypatch):
    from app.infra.attempt.title import title_attempt_impl

    owner = uuid4()
    group_id, session_id = uuid4(), uuid4()
    renamed = _wire_title(monkeypatch, _profile(owner, "member", 1))
    _wire_group_owner(
        monkeypatch, group_id=group_id, session_id=session_id,
        owner_profile_id=owner, department_in_scope=False,
    )
    await title_attempt_impl(
        _FakePool(), object(), profile_id=owner, session_id=session_id,
        group_id=group_id, title="mine",
    )
    assert renamed == [group_id]


# ─────────────────────────────────────────────────────────────────────────────
# call_download / video_download (media IDOR siblings)
# ─────────────────────────────────────────────────────────────────────────────


def _upload(upload_id, session_id, file_path):
    from app.tools.entries.uploads.types import GetUploadResponse

    return GetUploadResponse(
        id=upload_id, session_id=session_id, file_path=file_path,
        mime_type="audio/webm", size=3, created_at=datetime.now(UTC),
        active=True, mcp=False, generated=False,
    )


def _wire_media_owner(monkeypatch, *, upload_id, session_id, owner_profile_id,
                      department_in_scope=True):
    """Patch the gate's late-imported owner-resolution (upload → session → owner)."""
    import app.infra.dashboard.visibility as vis_mod
    import app.tools.entries.sessions.get as sessions_get
    import app.tools.entries.uploads.get as uploads_get

    async def fake_get_upload(conn, uid, redis, *, bypass_cache=False):
        return _upload(upload_id, session_id, "media.webm")

    async def fake_get_sessions(conn, ids, redis, *a, **k):
        return [_session(session_id, owner_profile_id)]

    async def fake_in_scope(pool, caller, owner_profiles_id, *a, **k):
        return department_in_scope

    monkeypatch.setattr(uploads_get, "get_upload", fake_get_upload)
    monkeypatch.setattr(sessions_get, "get_sessions", fake_get_sessions)
    monkeypatch.setattr(vis_mod, "is_profile_in_department_scope", fake_in_scope)


def _real_disk(monkeypatch, module, folder_attr, filename):
    import tempfile

    d = tempfile.mkdtemp()
    with open(os.path.join(d, filename), "wb") as fh:
        fh.write(b"DAT")
    monkeypatch.setattr(module, folder_attr, d)
    return d


def _wire_call_download(monkeypatch, *, actor, upload_id, session_id):
    import app.infra.attempt.call_download as mod
    from app.tools.entries.call_uploads.types import GetCallUploadResponse

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_search_call_uploads(conn, redis, *, call_ids=None, limit=1, **k):
        return [
            GetCallUploadResponse(
                id=uuid4(), call_id=call_ids[0], upload_id=upload_id,
                session_id=session_id, created_at=datetime.now(UTC),
                active=True, mcp=False, generated=False,
            )
        ]

    async def fake_get_upload(conn, uid, redis, *, bypass_cache=False):
        return _upload(upload_id, session_id, "media.webm")

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "search_call_uploads", fake_search_call_uploads)
    monkeypatch.setattr(mod, "get_upload", fake_get_upload)
    _real_disk(monkeypatch, mod, "CALL_FOLDER", "media.webm")
    return mod


async def test_call_download_blocks_peer_member(monkeypatch):
    from app.infra.attempt.call_download import call_download_attempt_impl

    attacker, owner = uuid4(), uuid4()
    upload_id, session_id, call_id = uuid4(), uuid4(), uuid4()
    actor = _profile(attacker, "member", 1)
    _wire_call_download(monkeypatch, actor=actor, upload_id=upload_id, session_id=session_id)
    _wire_media_owner(
        monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner
    )
    with pytest.raises(HTTPException) as exc:
        await call_download_attempt_impl(
            _FakePool(), object(), profile_id=attacker, call_id=call_id,
        )
    assert exc.value.status_code == 403


async def test_call_download_allows_owner(monkeypatch):
    from app.infra.attempt.call_download import call_download_attempt_impl

    owner = uuid4()
    upload_id, session_id, call_id = uuid4(), uuid4(), uuid4()
    actor = _profile(owner, "member", 1)
    _wire_call_download(monkeypatch, actor=actor, upload_id=upload_id, session_id=session_id)
    _wire_media_owner(
        monkeypatch, upload_id=upload_id, session_id=session_id,
        owner_profile_id=owner, department_in_scope=False,
    )
    result = await call_download_attempt_impl(
        _FakePool(), object(), profile_id=owner, call_id=call_id,
    )
    assert result.upload_id == upload_id


def _wire_video_download(monkeypatch, *, actor, upload_id, session_id):
    import app.infra.attempt.video_download as mod
    from app.tools.entries.videos.types import SearchVideoResponse

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_search_videos(conn, redis, *, videos_ids=None, limit=1, **k):
        return [
            SearchVideoResponse.model_construct(
                video_id=uuid4(), videos_id=videos_ids[0], upload_id=upload_id,
                file_path="media.webm", mime_type="video/webm", size=3,
                length_seconds=0, created_at=datetime.now(UTC),
            )
        ]

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "search_videos", fake_search_videos)
    _real_disk(monkeypatch, mod, "UPLOAD_FOLDER", "media.webm")
    return mod


async def test_video_download_blocks_peer_member(monkeypatch):
    from app.infra.attempt.video_download import video_download_attempt_impl

    attacker, owner = uuid4(), uuid4()
    upload_id, session_id, video_id = uuid4(), uuid4(), uuid4()
    actor = _profile(attacker, "member", 1)
    _wire_video_download(monkeypatch, actor=actor, upload_id=upload_id, session_id=session_id)
    _wire_media_owner(
        monkeypatch, upload_id=upload_id, session_id=session_id, owner_profile_id=owner
    )
    with pytest.raises(HTTPException) as exc:
        await video_download_attempt_impl(
            _FakePool(), object(), profile_id=attacker, video_id=video_id,
        )
    assert exc.value.status_code == 403


async def test_video_download_allows_higher_role_in_scope(monkeypatch):
    from app.infra.attempt.video_download import video_download_attempt_impl

    instructor, owner = uuid4(), uuid4()
    upload_id, session_id, video_id = uuid4(), uuid4(), uuid4()
    actor = _profile(instructor, "instructional", 2)
    _wire_video_download(monkeypatch, actor=actor, upload_id=upload_id, session_id=session_id)
    _wire_media_owner(
        monkeypatch, upload_id=upload_id, session_id=session_id,
        owner_profile_id=owner, department_in_scope=True,
    )
    result = await video_download_attempt_impl(
        _FakePool(), object(), profile_id=instructor, video_id=video_id,
    )
    assert result.upload_id == upload_id
