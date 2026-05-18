"""Tests for app.utils.storage.range_response."""

import os
import tempfile

from app.utils.storage.range_response import create_range_response


def _make_temp_file(content: bytes) -> str:
    """Write content to a temp file and return its path."""
    fd, path = tempfile.mkstemp()
    os.write(fd, content)
    os.close(fd)
    return path


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
