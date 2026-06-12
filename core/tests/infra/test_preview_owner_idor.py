"""C2 — class-fix: every ``*_preview`` impl scopes to the upload owner.

The R2 download class-fix (``enforce_upload_owner``, see
``test_download_owner_idor.py``) covered all ``*_download`` impls but missed the
parallel ``*_preview`` class, which renders the SAME session-owned upload bytes
(the PDF first-page PNG) by a caller-supplied resource id, gated only by a
role-level ``has_permission`` check. So a dept-A admin/instructor holding
``<artifact>:file_preview`` could render a dept-B session's upload first page
(cross-dept read IDOR).

This suite exercises every guarded preview impl — ``document`` / ``scenario`` /
``group`` (the ``attempt`` preview is scoped via ``enforce_attempt_media_access``,
like the attempt download family, and is not part of this sweep). For each:
OWNER (the upload's session is the caller's) is ALLOWED and reaches the rendered
bytes; a CROSS-DEPT / cross-owner caller holding the permission is DENIED with
404 and never renders. All unit-level (monkeypatched), no DB.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.profile_identity_context import ProfileIdentityContext

pytestmark = pytest.mark.asyncio

OWNER_MODULE = "app.infra.upload_owner"


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


class _FileRow:
    """A files_mv row + its get_file counterpart's session_id."""

    def __init__(self, entry_id, session_id, upload_id, file_path):
        self.file_id = entry_id
        self.session_id = session_id
        self.upload_id = upload_id
        self.file_path = file_path
        self.mime_type = "application/pdf"
        self.size = 2


class _Session:
    def __init__(self, sid):
        self.id = sid


def _patch_sessions(monkeypatch, owned_session_ids):
    async def mock_search_sessions(conn, redis, profile_ids=None, **kw):
        return [_Session(s) for s in owned_session_ids]

    monkeypatch.setattr(f"{OWNER_MODULE}.search_sessions", mock_search_sessions)


@pytest.mark.parametrize(
    "module,func,artifact,op",
    [
        ("app.infra.document.file_preview", "file_preview_document_impl",
         "document", "file_preview"),
        ("app.infra.scenario.file_preview", "file_preview_scenario_impl",
         "scenario", "file_preview"),
        # group's preview checks the "system" artifact permission (per impl).
        ("app.infra.group.file_preview", "file_preview_group_impl",
         "system", "file_preview"),
    ],
)
async def test_preview_owner_allow_cross_deny(
    monkeypatch, tmp_path, module, func, artifact, op
):
    mod = __import__(module, fromlist=[func])
    impl = getattr(mod, func)

    upload_id = uuid4()
    f = tmp_path / "blob.pdf"
    f.write_text("%PDF-1.4 fake")
    owner_session = uuid4()
    entry_id = uuid4()
    row = _FileRow(entry_id, owner_session, upload_id, f.name)

    # grant both names to be robust to the artifact the impl actually checks.
    perms = [(artifact, op), ("document", op), ("scenario", op), ("system", op)]

    async def mock_resolve(pool, pid, redis, **kw):
        return _profile(uuid4(), perms=perms, dept=uuid4())

    async def mock_search(conn, redis, **kw):
        return [row]

    async def mock_get_file(conn, rid, redis):
        return row

    sentinel = b"PNGBYTES"

    def mock_render(path):
        return sentinel

    monkeypatch.setattr(f"{module}.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr(f"{module}.search_files", mock_search)
    monkeypatch.setattr(f"{module}.get_file", mock_get_file)
    monkeypatch.setattr(f"{module}.pdf_first_page_to_image_bytes", mock_render)
    monkeypatch.setattr(mod, "UPLOAD_FOLDER", str(tmp_path))

    # ALLOW: the file's owning session is the caller's → renders the bytes.
    _patch_sessions(monkeypatch, [owner_session])
    result = await impl(_Pool(), None, profile_id=uuid4(), file_id=uuid4())
    # document returns raw bytes; scenario/group return a result carrying bytes.
    preview = result if isinstance(result, (bytes, bytearray)) else result.preview_bytes
    assert preview == sentinel

    # DENY (cross-dept/cross-owner): caller owns only foreign sessions → 404,
    # and the renderer is never reached.
    _patch_sessions(monkeypatch, [uuid4(), uuid4()])

    def mock_render_must_not(path):
        raise AssertionError("must not render bytes for a foreign upload")

    monkeypatch.setattr(
        f"{module}.pdf_first_page_to_image_bytes", mock_render_must_not
    )
    with pytest.raises(HTTPException) as exc:
        await impl(_Pool(), None, profile_id=uuid4(), file_id=uuid4())
    assert exc.value.status_code == 404
