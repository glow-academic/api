"""Tests for app.utils.storage.range_response."""

import os
import tempfile

import pytest

from app.utils.storage.range_response import create_range_response


def _make_temp_file(content: bytes) -> str:
    """Write content to a temp file and return its path."""
    fd, path = tempfile.mkstemp()
    os.write(fd, content)
    os.close(fd)
    return path


async def _collect_body(resp) -> bytes:
    """Drain a StreamingResponse body (Starlette wraps sync gens as async)."""
    body_iter = resp.body_iterator
    if hasattr(body_iter, "__aiter__"):
        return b"".join([chunk async for chunk in body_iter])
    return b"".join(list(body_iter))


def test_full_response_status_200():
    """Without a range header, status code is 200."""
    path = _make_temp_file(b"hello world")
    try:
        resp = create_range_response(
            file_path=path,
            content_type="text/plain",
            content_disposition="inline",
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Length"] == str(len(b"hello world"))
    finally:
        os.unlink(path)


def test_range_request_status_206():
    """With a Range header, status code is 206."""
    path = _make_temp_file(b"0123456789")
    try:
        resp = create_range_response(
            file_path=path,
            content_type="text/plain",
            content_disposition="inline",
            range_header="bytes=0-4",
        )
        assert resp.status_code == 206
        assert resp.headers["Content-Length"] == "5"
        assert "Content-Range" in resp.headers
    finally:
        os.unlink(path)


def test_range_response_content_range_header():
    """Content-Range header has correct format."""
    data = b"abcdefghij"  # 10 bytes
    path = _make_temp_file(data)
    try:
        resp = create_range_response(
            file_path=path,
            content_type="application/octet-stream",
            content_disposition="attachment",
            range_header="bytes=2-5",
        )
        assert resp.headers["Content-Range"] == "bytes 2-5/10"
        assert resp.headers["Content-Length"] == "4"
    finally:
        os.unlink(path)


def test_accept_ranges_header_present():
    """Accept-Ranges: bytes is always present."""
    path = _make_temp_file(b"data")
    try:
        resp = create_range_response(
            file_path=path,
            content_type="text/plain",
            content_disposition="inline",
        )
        assert resp.headers["Accept-Ranges"] == "bytes"
    finally:
        os.unlink(path)


def test_range_beyond_file_size_clamped():
    """A range end beyond file size is clamped to file_size - 1."""
    data = b"short"  # 5 bytes
    path = _make_temp_file(data)
    try:
        resp = create_range_response(
            file_path=path,
            content_type="text/plain",
            content_disposition="inline",
            range_header="bytes=0-999",
        )
        assert resp.status_code == 206
        # end clamped to 4, so length is 5
        assert resp.headers["Content-Length"] == "5"
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_open_ended_range_to_eof():
    """`bytes=N-` serves from N through the last byte."""
    data = bytes(range(256)) * 4  # 1024 bytes
    path = _make_temp_file(data)
    try:
        resp = create_range_response(
            file_path=path,
            content_type="application/octet-stream",
            content_disposition="inline",
            range_header="bytes=500-",
        )
        assert resp.status_code == 206
        assert resp.headers["Content-Range"] == "bytes 500-1023/1024"
        assert resp.headers["Content-Length"] == str(1024 - 500)
        assert await _collect_body(resp) == data[500:]
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_first_500_bytes_normal_range():
    """`bytes=0-499` serves exactly the first 500 bytes."""
    data = bytes(range(256)) * 4  # 1024 bytes
    path = _make_temp_file(data)
    try:
        resp = create_range_response(
            file_path=path,
            content_type="application/octet-stream",
            content_disposition="inline",
            range_header="bytes=0-499",
        )
        assert resp.status_code == 206
        assert resp.headers["Content-Range"] == "bytes 0-499/1024"
        assert resp.headers["Content-Length"] == "500"
        assert await _collect_body(resp) == data[:500]
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_suffix_range_serves_last_n_bytes():
    """`bytes=-500` serves the LAST 500 bytes (RFC 7233 suffix range).

    Regression: previously returned the FIRST 501 bytes with a bogus
    `Content-Range: bytes 0-500/...`, breaking media seeking / PDF.js.
    """
    data = bytes(range(256)) * 4  # 1024 bytes
    path = _make_temp_file(data)
    try:
        resp = create_range_response(
            file_path=path,
            content_type="application/octet-stream",
            content_disposition="inline",
            range_header="bytes=-500",
        )
        assert resp.status_code == 206
        # last 500 bytes => offsets 524..1023
        assert resp.headers["Content-Range"] == "bytes 524-1023/1024"
        assert resp.headers["Content-Length"] == "500"
        assert await _collect_body(resp) == data[-500:]
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_suffix_range_larger_than_file_serves_whole_file():
    """`bytes=-N` with N >= size serves the entire representation."""
    data = b"abcdef"  # 6 bytes
    path = _make_temp_file(data)
    try:
        resp = create_range_response(
            file_path=path,
            content_type="text/plain",
            content_disposition="inline",
            range_header="bytes=-100",
        )
        assert resp.status_code == 206
        assert resp.headers["Content-Range"] == "bytes 0-5/6"
        assert resp.headers["Content-Length"] == "6"
        assert await _collect_body(resp) == data
    finally:
        os.unlink(path)


def test_inverted_range_returns_416():
    """`bytes=500-100` (start > end) is unsatisfiable -> 416, not a 206."""
    data = bytes(1024)
    path = _make_temp_file(data)
    try:
        resp = create_range_response(
            file_path=path,
            content_type="application/octet-stream",
            content_disposition="inline",
            range_header="bytes=500-100",
        )
        assert resp.status_code == 416
        assert resp.headers["Content-Range"] == "bytes */1024"
        assert resp.headers["Accept-Ranges"] == "bytes"
    finally:
        os.unlink(path)


def test_start_beyond_file_size_returns_416():
    """A start at or past EOF is unsatisfiable -> 416."""
    data = b"short"  # 5 bytes
    path = _make_temp_file(data)
    try:
        resp = create_range_response(
            file_path=path,
            content_type="text/plain",
            content_disposition="inline",
            range_header="bytes=5000-6000",
        )
        assert resp.status_code == 416
        assert resp.headers["Content-Range"] == "bytes */5"
    finally:
        os.unlink(path)


def test_nosniff_header_on_full_200_response():
    """Every full (200) download carries X-Content-Type-Options: nosniff.

    Defense-in-depth against stored XSS on download: the browser must never
    MIME-sniff a client-typed upload into text/html and execute it.
    """
    path = _make_temp_file(b"<html><script>alert(1)</script></html>")
    try:
        resp = create_range_response(
            file_path=path,
            content_type="text/html",
            content_disposition="attachment",
        )
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
    finally:
        os.unlink(path)


def test_nosniff_header_on_partial_206_response():
    """Range (206) responses also carry X-Content-Type-Options: nosniff."""
    path = _make_temp_file(b"0123456789")
    try:
        resp = create_range_response(
            file_path=path,
            content_type="text/html",
            content_disposition="attachment",
            range_header="bytes=0-4",
        )
        assert resp.status_code == 206
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
    finally:
        os.unlink(path)


def test_nosniff_header_on_416_response():
    """Unsatisfiable-range (416) responses also carry nosniff."""
    path = _make_temp_file(b"short")
    try:
        resp = create_range_response(
            file_path=path,
            content_type="text/html",
            content_disposition="attachment",
            range_header="bytes=5000-6000",
        )
        assert resp.status_code == 416
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
    finally:
        os.unlink(path)
