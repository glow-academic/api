"""Shared range-streaming download response.

Supports HTTP Range requests for all file types — audio seeking, video
scrubbing, PDF partial loads, etc.  Returns 206 Partial Content when a
Range header is present, 200 otherwise.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from fastapi import Response
from fastapi.responses import StreamingResponse

_CHUNK_SIZE = 1024 * 1024  # 1 MB


def _iter_file(path: str, start: int, length: int) -> Iterator[bytes]:
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            data = f.read(min(_CHUNK_SIZE, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def create_range_response(
    *,
    file_path: str,
    content_type: str,
    content_disposition: str,
    range_header: str | None = None,
) -> Response:
    """Create a streaming response with optional HTTP Range support."""
    file_size = os.path.getsize(file_path)
    start = 0
    end = file_size - 1

    if range_header:
        range_spec = range_header.replace("bytes=", "")
        if "-" in range_spec:
            parts = range_spec.split("-")
            if parts[0]:
                start = int(parts[0])
            if parts[1]:
                end = int(parts[1])

    if start >= file_size:
        start = 0
    if end >= file_size:
        end = file_size - 1

    content_length = end - start + 1

    return StreamingResponse(
        _iter_file(file_path, start, content_length),
        status_code=206 if range_header else 200,
        media_type=content_type,
        headers={
            "Content-Disposition": content_disposition,
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Cache-Control": "private, max-age=0, must-revalidate",
        },
    )
