"""Resource-exhaustion guard at the route boundary: upload routes cap body size.

The #260 sweep wired ``read_upload_bounded`` into every remaining uncapped
upload route (18 CSV imports + document image/file/text + scenario image/video).
Each previously did ``file_bytes = await file.read()`` — materializing the whole
request body before any size check. A streamed multi-GB body could exhaust
server memory (and disk) before anything rejected it.

These tests drive the *actual route handlers* with a fake ``UploadFile`` and
deps-as-params (the pool/redis/audit-wrapper are stubbed via monkeypatch, the
request state is a tiny stub) so no DB/redis/testcontainers are touched. They
cover the two distinct shapes — the CSV import path and the binary-upload path:

  * an over-cap body is rejected with HTTP 413 *before* the read fully
    materializes (an exploding upload proves the unbounded read never happens),
  * an under-cap body flows through ``read_upload_bounded`` into the existing
    parse/runner path unchanged (the bytes reach the impl).
"""

from __future__ import annotations

import asyncio
import types

import pytest
from fastapi import HTTPException

import app.routes.agent.csv as agent_csv_route
import app.routes.document.image_upload as document_image_route
from app.infra.shared_types import MAX_CSV_UPLOAD_BYTES, MAX_UPLOAD_BYTES


def _run(coro):
    return asyncio.run(coro)


class _RequestStub:
    """Minimal ``Request`` stand-in: only ``state`` (profile/session) + ``url``."""

    def __init__(self, *, profile_id: str | None = "p-1", session_id: str | None = None):
        self.state = types.SimpleNamespace(profile_id=profile_id, session_id=session_id)
        self.url = types.SimpleNamespace(path="/test")
        self.method = "POST"
        self.headers: dict[str, str] = {}


class _ResponseStub:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


class _FakeUpload:
    """``UploadFile`` stand-in: serves ``data`` via async ``read(size)``."""

    def __init__(self, data: bytes, *, filename: str = "f.csv", content_type: str = "text/csv"):
        self._data = data
        self._pos = 0
        self.filename = filename
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


class _ExplodingUpload:
    """Yields chunks up to just past ``max_bytes``, then explodes — proves the
    bounded read aborts at the cap instead of draining the whole body."""

    def __init__(self, *, max_bytes: int, filename: str, content_type: str):
        self._budget = max_bytes + 2 * 1024 * 1024  # a couple chunks past the cap
        self._served = 0
        self.filename = filename
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        step = size if size and size > 0 else 1024 * 1024
        if self._served >= self._budget:
            raise AssertionError("read past the cap — body was fully materialized")
        self._served += step
        return b"x" * step


# ---------------------------------------------------------------------------
# CSV import shape — agent/csv as the representative
# ---------------------------------------------------------------------------


def test_csv_route_rejects_over_cap_with_413(monkeypatch) -> None:
    """An over-cap CSV upload is rejected 413 before the read materializes.

    ``session_id=None`` skips the group lookup so the bounded read is the first
    thing reached after the deps are resolved; the exploding upload guarantees
    the read aborts at the cap rather than draining the whole (multi-GB) body."""
    monkeypatch.setattr(agent_csv_route, "get_pool", lambda: object())
    monkeypatch.setattr(agent_csv_route, "get_redis_client", lambda: object())
    monkeypatch.setattr(agent_csv_route, "get_upload_folder", lambda: "/tmp")

    upload = _ExplodingUpload(
        max_bytes=MAX_CSV_UPLOAD_BYTES, filename="big.csv", content_type="text/csv"
    )
    with pytest.raises(HTTPException) as exc:
        _run(
            agent_csv_route.parse_agent_csv(
                _RequestStub(), file=upload, idempotency_key=None, soft=False, accept=None
            )
        )
    assert exc.value.status_code == 413


def test_csv_route_passes_under_cap_bytes_to_runner(monkeypatch) -> None:
    """An under-cap CSV flows through the bounded read into the parse runner —
    the exact bytes reach the impl, proving the cap doesn't alter the payload."""
    captured: dict = {}

    async def _fake_audit(*args, runner, **kwargs):
        return await runner()

    async def _fake_impl(pool, *, file_bytes, **kwargs):
        captured["file_bytes"] = file_bytes
        return "ok"

    monkeypatch.setattr(agent_csv_route, "get_pool", lambda: object())
    monkeypatch.setattr(agent_csv_route, "get_redis_client", lambda: object())
    monkeypatch.setattr(agent_csv_route, "get_upload_folder", lambda: "/tmp")
    monkeypatch.setattr(agent_csv_route, "run_artifact_operation_with_audit", _fake_audit)
    monkeypatch.setattr(agent_csv_route, "parse_agent_csv_impl", _fake_impl)

    payload = b"name,description\nAlpha,first\nBeta,second\n"
    upload = _FakeUpload(payload, filename="ok.csv", content_type="text/csv")
    result = _run(
        agent_csv_route.parse_agent_csv(
            _RequestStub(), file=upload, idempotency_key=None, soft=False, accept=None
        )
    )
    assert result == "ok"
    assert captured["file_bytes"] == payload


# ---------------------------------------------------------------------------
# Binary-upload shape — document/image_upload as the representative
# ---------------------------------------------------------------------------


def test_binary_route_rejects_over_cap_with_413(monkeypatch) -> None:
    """An over-cap image upload is rejected 413 before the read materializes."""
    monkeypatch.setattr(document_image_route, "get_pool", lambda: object())
    monkeypatch.setattr(document_image_route, "get_redis_client", lambda: object())
    monkeypatch.setattr(document_image_route, "get_upload_folder", lambda: "/tmp")

    upload = _ExplodingUpload(
        max_bytes=MAX_UPLOAD_BYTES, filename="big.png", content_type="image/png"
    )
    with pytest.raises(HTTPException) as exc:
        _run(
            document_image_route.upload_image(
                _RequestStub(),
                _ResponseStub(),
                file=upload,
                name=None,
                description=None,
                idempotency_key=None,
                soft=False,
                accept=None,
            )
        )
    assert exc.value.status_code == 413


def test_binary_route_passes_under_cap_bytes_to_runner(monkeypatch) -> None:
    """An under-cap image flows through the bounded read into the impl runner."""
    captured: dict = {}

    async def _fake_audit(*args, runner, **kwargs):
        return await runner()

    async def _fake_impl(pool, redis, *, file_bytes, **kwargs):
        captured["file_bytes"] = file_bytes
        return "ok"

    monkeypatch.setattr(document_image_route, "get_pool", lambda: object())
    monkeypatch.setattr(document_image_route, "get_redis_client", lambda: object())
    monkeypatch.setattr(document_image_route, "get_upload_folder", lambda: "/tmp")
    monkeypatch.setattr(
        document_image_route, "run_artifact_operation_with_audit", _fake_audit
    )
    monkeypatch.setattr(document_image_route, "image_upload_document_impl", _fake_impl)

    payload = b"\x89PNG\r\n\x1a\n" + b"pixels" * 100
    upload = _FakeUpload(payload, filename="ok.png", content_type="image/png")
    result = _run(
        document_image_route.upload_image(
            _RequestStub(),
            _ResponseStub(),
            file=upload,
            name=None,
            description=None,
            idempotency_key=None,
            soft=False,
            accept=None,
        )
    )
    assert result == "ok"
    assert captured["file_bytes"] == payload
