"""Resource-exhaustion guard: file uploads cap the byte size.

Every upload route (audio/image/document/CSV) used to materialize the whole
request body with a single ``file_bytes = await file.read()`` *before* any size
check, then write those bytes to disk. An authenticated client could stream a
multi-GB body and exhaust server memory (and disk) before anything rejected it.
``read_upload_bounded`` closes that gap: it pulls the body one chunk at a time
and aborts the moment the cumulative size crosses the cap, so the oversized
read never completes.

This is a pure helper test — the upload object (anything with an async
``read(size)``) and the error factory are the explicit deps, passed in via a
stub + parametrize. No DB/redis/FastAPI app.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.infra.shared_types import (
    MAX_UPLOAD_BYTES,
    read_upload_bounded,
)


class _FakeUpload:
    """Minimal ``UploadFile`` stand-in: serves ``data`` via async ``read(size)``."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


# (label, error factory, expected exception type). Mirrors how each route wires
# its own client-facing error: ValueError default and the HTTPException(413)
# lambda the upload routes use.
ERROR_FACTORIES = [
    ("default_valueerror", None, ValueError),
    (
        "http_exception",
        lambda msg: HTTPException(status_code=413, detail=msg),
        HTTPException,
    ),
]


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("label, factory, exc_type", ERROR_FACTORIES)
def test_under_cap_read_in_full(label, factory, exc_type) -> None:
    """A small body (the common case) is read back unchanged."""
    payload = b"hello world" * 100
    upload = _FakeUpload(payload)
    result = _run(read_upload_bounded(upload, make_error=factory, chunk_size=64))
    assert result == payload


@pytest.mark.parametrize("label, factory, exc_type", ERROR_FACTORIES)
def test_at_cap_accepted(label, factory, exc_type) -> None:
    """A body exactly at the cap is accepted (boundary is inclusive)."""
    payload = b"x" * 1024
    upload = _FakeUpload(payload)
    result = _run(
        read_upload_bounded(upload, make_error=factory, max_bytes=1024, chunk_size=128)
    )
    assert result == payload


@pytest.mark.parametrize("label, factory, exc_type", ERROR_FACTORIES)
def test_over_cap_rejected(label, factory, exc_type) -> None:
    """One byte past the cap is rejected with the caller's own error type."""
    payload = b"x" * 1025
    upload = _FakeUpload(payload)
    with pytest.raises(exc_type):
        _run(
            read_upload_bounded(
                upload, make_error=factory, max_bytes=1024, chunk_size=128
            )
        )


def test_http_exception_is_413() -> None:
    """The route-wired factory yields a 413 Payload Too Large."""
    upload = _FakeUpload(b"x" * 2048)
    with pytest.raises(HTTPException) as exc_info:
        _run(
            read_upload_bounded(
                upload,
                make_error=lambda msg: HTTPException(status_code=413, detail=msg),
                max_bytes=1024,
            )
        )
    assert exc_info.value.status_code == 413


def test_rejects_before_full_materialization() -> None:
    """The read aborts *as soon as* the cap is crossed — it does not drain the
    whole body first. A reader that explodes once read past the cap must still
    raise the clean cap error, proving the unbounded read never happens."""

    class _ExplodingUpload:
        """Yields chunks up to just past the cap, then explodes if read further."""

        def __init__(self, max_bytes: int, chunk_size: int) -> None:
            self._budget = max_bytes + chunk_size  # one chunk past the cap
            self._chunk_size = chunk_size
            self._served = 0

        async def read(self, size: int = -1) -> bytes:
            if self._served >= self._budget:
                raise AssertionError(
                    "read past the cap — body was fully materialized"
                )
            self._served += self._chunk_size
            return b"x" * self._chunk_size

    upload = _ExplodingUpload(max_bytes=1024, chunk_size=256)
    with pytest.raises(ValueError):
        _run(read_upload_bounded(upload, max_bytes=1024, chunk_size=256))


def test_default_cap_is_64_mib() -> None:
    """The shipped default is a sane 64 MiB ceiling on per-request memory."""
    assert MAX_UPLOAD_BYTES == 64 * 1024 * 1024
