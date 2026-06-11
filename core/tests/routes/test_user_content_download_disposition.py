"""User-content file_download routes must force ``attachment`` + nosniff.

Stored-XSS-on-download hardening: the 4 user-content download routes
(document/system/attempt/scenario) previously served the client-controlled
``content_type`` with ``Content-Disposition: inline`` and no nosniff. A user
with upload permission could store an .html/SVG typed ``text/html`` and have it
rendered as script in the app origin by opening the same-origin download link.

These tests drive each thin route handler with its blob-resolving impl, audit
runner, group resolver and globals monkeypatched (DB/redis-free, deterministic),
place a real ``text/html`` file on disk, and assert the emitted response:

  * ``Content-Disposition`` is ``attachment`` (never ``inline``), so the
    browser downloads rather than renders user content; and
  * ``X-Content-Type-Options: nosniff`` is present (range_response sets it for
    every download), so a mistyped attachment can't be sniffed into HTML.
"""

from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


# Each user-content route, its module path, and the names of the symbols that
# module imports (and that we therefore patch on *that* module's namespace).
_ROUTES = [
    (
        "app.routes.document.file_download",
        "file_download_document_impl",
        "group_document_impl",
    ),
    (
        "app.routes.system.file_download",
        "file_download_group_impl",
        "group_system_impl",
    ),
    (
        "app.routes.attempt.file_download",
        "file_download_attempt_impl",
        "group_attempt_impl",
    ),
    (
        "app.routes.scenario.file_download",
        "file_download_scenario_impl",
        "group_scenario_impl",
    ),
]


def _make_html_file() -> str:
    fd, path = tempfile.mkstemp(suffix=".html")
    os.write(fd, b"<html><script>alert(document.cookie)</script></html>")
    os.close(fd)
    return path


@pytest.mark.parametrize("module_path,impl_name,group_name", _ROUTES)
async def test_user_content_download_is_attachment_with_nosniff(
    module_path, impl_name, group_name, monkeypatch
):
    """A text/html upload downloads as attachment + nosniff, never inline."""
    import importlib

    mod = importlib.import_module(module_path)
    file_path = _make_html_file()
    try:
        # Resolved blob: a real on-disk html file the client uploaded with a
        # malicious text/html content_type.
        result = SimpleNamespace(
            file_path=file_path,
            content_type="text/html",
            filename="evil.html",
        )

        async def _fake_impl(*_args, **_kwargs):
            return result

        async def _fake_group(*_args, **_kwargs):
            return SimpleNamespace(group_id=uuid4())

        async def _fake_audit(*_args, runner=None, **_kwargs):
            return await runner()

        monkeypatch.setattr(mod, impl_name, _fake_impl)
        monkeypatch.setattr(mod, group_name, _fake_group)
        monkeypatch.setattr(mod, "run_artifact_operation_with_audit", _fake_audit)
        monkeypatch.setattr(mod, "get_pool", lambda: object())
        monkeypatch.setattr(mod, "get_redis_client", lambda: object())
        monkeypatch.setattr(mod, "get_upload_folder", lambda: None)

        http_request = SimpleNamespace(
            state=SimpleNamespace(profile_id=uuid4(), session_id=uuid4()),
            headers={},
            url=SimpleNamespace(path="/x/file_download"),
        )
        api_request = SimpleNamespace(file_id=uuid4())

        resp = await mod.download_file(
            api_request, http_request, SimpleNamespace()
        )

        disposition = resp.headers["Content-Disposition"]
        assert disposition.startswith("attachment"), (
            f"{module_path} must force attachment, got: {disposition}"
        )
        assert "inline" not in disposition
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
    finally:
        os.unlink(file_path)
