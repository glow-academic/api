"""R2 — class-fix: every artifact ``*_download`` impl scopes to the upload owner.

Generalizes the SEC2 provider/call_download fix via the shared
``enforce_upload_owner`` helper. These impls resolve a session-owned upload by
a caller-supplied resource id, gated only by a role-level ``has_permission``
check — so a dept-A admin/instructor holding ``<artifact>:<kind>_download``
could download a dept-B session's bytes (cross-dept read IDOR).

This suite exercises a representative impl per resolution shape + upload kind:

  * junction (search_*_uploads → .session_id):  call (agent), text (persona),
    audio (group)
  * MV resource (search_* → get_* → .session_id): file (model),
    image (scenario), video (group)

For each: OWNER (the upload's session is the caller's) is ALLOWED; a
CROSS-DEPT / cross-owner caller holding the permission is DENIED with 404 and
never reaches the bytes. All unit-level (monkeypatched), no DB.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.profile_identity_context import ProfileIdentityContext

pytestmark = pytest.mark.asyncio

OWNER_MODULE = "app.infra.upload_owner"


# --------------------------------------------------------------------------
# Shared doubles
# --------------------------------------------------------------------------
def _profile(profiles_id, *, perms, dept):
    return ProfileIdentityContext(
        profiles_id=profiles_id,
        name="Admin",
        role="admin",
        role_name="Administrator",
        role_description="",
        role_artifacts=[],
        primary_email="a@example.com",
        emails=["a@example.com"],
        primary_department_id=dept,
        department_ids=[dept],
        settings_id=uuid4(),
        request_limit=100,
        request_limit_interval=None,
        is_active=True,
        role_level=1,  # dept-scoped admin (NOT super-admin)
        role_permissions=perms,
    )


class _Pool:
    class _Conn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    def acquire(self):
        return self._Conn()


class _Junction:
    def __init__(self, session_id, upload_id):
        self.session_id = session_id
        self.upload_id = upload_id


class _Resource:
    """A files/images/videos MV row + its get_* counterpart's session_id."""

    def __init__(self, entry_id, session_id, upload_id, file_path):
        self.file_id = entry_id
        self.image_id = entry_id
        self.video_id = entry_id
        self.text_id = entry_id
        self.session_id = session_id
        self.upload_id = upload_id
        self.file_path = file_path
        self.mime_type = "application/octet-stream"
        self.size = 2


class _Session:
    def __init__(self, sid):
        self.id = sid


class _Upload:
    def __init__(self, upload_id, file_path):
        self.id = upload_id
        self.file_path = file_path
        self.mime_type = "application/octet-stream"
        self.size = 2


def _patch_sessions(monkeypatch, owned_session_ids):
    async def mock_search_sessions(conn, redis, profile_ids=None, **kw):
        return [_Session(s) for s in owned_session_ids]

    monkeypatch.setattr(f"{OWNER_MODULE}.search_sessions", mock_search_sessions)


# --------------------------------------------------------------------------
# Junction-shaped impls (call / text / audio)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "module,func,id_kw,artifact,op,search_attr",
    [
        ("app.infra.agent.call_download", "call_download_agent_impl",
         "call_id", "agent", "call_download", "search_call_uploads"),
        ("app.infra.persona.text_download", "text_download_persona_impl",
         "text_id", "persona", "text_download", "search_text_uploads"),
        ("app.infra.group.audio_download", "audio_download_group_impl",
         "audio_id", "group", "audio_download", "search_audio_uploads"),
    ],
)
async def test_junction_owner_allow_cross_deny(
    monkeypatch, tmp_path, module, func, id_kw, artifact, op, search_attr
):
    mod = __import__(module, fromlist=[func])
    impl = getattr(mod, func)

    upload_id = uuid4()
    f = tmp_path / "blob.bin"
    f.write_text("ok")
    junction = _Junction(session_id=uuid4(), upload_id=upload_id)

    async def mock_resolve(pool, pid, redis, **kw):
        # Some impls check the "system" artifact for the op; grant both so the
        # test exercises the OWNER gate, not the role gate.
        return _profile(
            uuid4(), perms=[(artifact, op), ("system", op)], dept=uuid4()
        )

    async def mock_search(conn, redis, **kw):
        return [junction]

    async def mock_get_upload(conn, uid, redis):
        return _Upload(upload_id, f.name)

    monkeypatch.setattr(f"{module}.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr(f"{module}.{search_attr}", mock_search)
    monkeypatch.setattr(f"{module}.get_upload", mock_get_upload)
    # serve any folder constant the impl uses off tmp_path
    for const in ("CALL_FOLDER", "UPLOAD_FOLDER", "AUDIO_FOLDER"):
        if hasattr(mod, const):
            monkeypatch.setattr(mod, const, str(tmp_path))

    # ALLOW: the upload's session is one of the caller's sessions.
    _patch_sessions(monkeypatch, [junction.session_id])
    result = await impl(_Pool(), None, profile_id=uuid4(), **{id_kw: uuid4()})
    assert result.upload_id == upload_id

    # DENY (cross-dept/cross-owner): caller owns only foreign sessions → 404.
    _patch_sessions(monkeypatch, [uuid4(), uuid4()])

    async def mock_get_upload_must_not(conn, uid, redis):
        raise AssertionError("must not reach the bytes for a foreign upload")

    monkeypatch.setattr(f"{module}.get_upload", mock_get_upload_must_not)
    with pytest.raises(HTTPException) as exc:
        await impl(_Pool(), None, profile_id=uuid4(), **{id_kw: uuid4()})
    assert exc.value.status_code == 404


# --------------------------------------------------------------------------
# MV-shaped impls (file / image / video)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "module,func,id_kw,artifact,op,search_attr,get_attr",
    [
        ("app.infra.model.file_download", "file_download_model_impl",
         "file_id", "model", "file_download", "search_files", "get_file"),
        ("app.infra.scenario.image_download", "image_download_scenario_impl",
         "image_id", "scenario", "image_download", "search_images", "get_image"),
        ("app.infra.group.video_download", "video_download_group_impl",
         "video_id", "group", "video_download", "search_videos", "get_video"),
    ],
)
async def test_mv_owner_allow_cross_deny(
    monkeypatch, tmp_path, module, func, id_kw, artifact, op, search_attr, get_attr
):
    mod = __import__(module, fromlist=[func])
    impl = getattr(mod, func)

    upload_id = uuid4()
    f = tmp_path / "blob.bin"
    f.write_text("ok")
    owner_session = uuid4()
    entry_id = uuid4()
    resource = _Resource(entry_id, owner_session, upload_id, f.name)

    # group impls check the "system" artifact permission (per impl source);
    # grant both to be robust to the artifact-name the impl actually checks.
    perms = [(artifact, op), ("system", op)]

    async def mock_resolve(pool, pid, redis, **kw):
        return _profile(uuid4(), perms=perms, dept=uuid4())

    async def mock_search(conn, redis, **kw):
        return [resource]

    async def mock_get(conn, rid, redis):
        return resource

    monkeypatch.setattr(f"{module}.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr(f"{module}.{search_attr}", mock_search)
    monkeypatch.setattr(f"{module}.{get_attr}", mock_get)
    for const in ("UPLOAD_FOLDER", "CALL_FOLDER"):
        if hasattr(mod, const):
            monkeypatch.setattr(mod, const, str(tmp_path))

    # ALLOW: the resource's owning session is the caller's.
    _patch_sessions(monkeypatch, [owner_session])
    result = await impl(_Pool(), None, profile_id=uuid4(), **{id_kw: uuid4()})
    assert result.upload_id == upload_id

    # DENY: caller owns only foreign sessions → 404, never serves the file.
    _patch_sessions(monkeypatch, [uuid4()])
    with pytest.raises(HTTPException) as exc:
        await impl(_Pool(), None, profile_id=uuid4(), **{id_kw: uuid4()})
    assert exc.value.status_code == 404


async def test_helper_fail_closed_on_missing_owner(monkeypatch):
    """enforce_upload_owner denies (404) when the owning session is unknown."""
    from app.infra.upload_owner import enforce_upload_owner

    _patch_sessions(monkeypatch, [uuid4()])
    # None owning session → cannot prove ownership → 404.
    with pytest.raises(HTTPException) as exc:
        await enforce_upload_owner(
            _Pool(), None,
            upload_session_id=None,
            requester=_profile(uuid4(), perms=[], dept=uuid4()),
            not_found_detail="nope",
        )
    assert exc.value.status_code == 404

    # None requester → 404.
    with pytest.raises(HTTPException) as exc:
        await enforce_upload_owner(
            _Pool(), None,
            upload_session_id=uuid4(),
            requester=None,
            not_found_detail="nope",
        )
    assert exc.value.status_code == 404
