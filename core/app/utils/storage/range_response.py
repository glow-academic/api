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

# Sentinel: the requested range cannot be satisfied (RFC 7233 -> 416).
_UNSATISFIABLE = object()


def _parse_range(range_header: str, file_size: int) -> object | tuple[int, int] | None:
    """Resolve a single HTTP Range request against a file size.

    Returns ``(start, end)`` (inclusive byte offsets) for a satisfiable range,
    ``None`` when the header is syntactically unusable and should be ignored
    (serve the full 200 representation), or ``_UNSATISFIABLE`` when the range
    is well-formed but cannot be served (caller should respond 416).
    """
    spec = range_header.replace("bytes=", "", 1).strip()
    # Only single ranges are supported; multi-range and malformed specs are
    # ignored (RFC 7233 allows a server to disregard a Range it can't parse).
    if "-" not in spec or "," in spec:
        return None

    first, _, last = spec.partition("-")
    try:
        if first == "":
            # Suffix range "bytes=-N": the final N bytes.
            suffix_len = int(last)
            if suffix_len <= 0:
                return _UNSATISFIABLE
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        else:
            start = int(first)
            end = int(last) if last else file_size - 1
    except ValueError:
        return None

    # Clamp the end to the last byte of the representation.
    if end >= file_size:
        end = file_size - 1

    # A start past EOF or an inverted range (start > end) is unsatisfiable.
    if start >= file_size or start > end:
        return _UNSATISFIABLE

    return start, end


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
    is_partial = False

    if range_header:
        parsed = _parse_range(range_header, file_size)
        if parsed is _UNSATISFIABLE:
            # RFC 7233 sec. 4.4: 416 with Content-Range stating the full size.
            return Response(
                status_code=416,
                headers={
                    "Content-Range": f"bytes */{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Disposition": content_disposition,
                    # Never let a browser MIME-sniff a download into an
                    # executable type (defense-in-depth against stored XSS
                    # on download). Applies to ALL download routes.
                    "X-Content-Type-Options": "nosniff",
                },
            )
        if parsed is not None:
            start, end = parsed  # type: ignore[misc]
            is_partial = True

    content_length = end - start + 1

    return StreamingResponse(
        _iter_file(file_path, start, content_length),
        status_code=206 if is_partial else 200,
        media_type=content_type,
        headers={
            "Content-Disposition": content_disposition,
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Cache-Control": "private, max-age=0, must-revalidate",
            # Never let a browser MIME-sniff a download into an executable
            # type (defense-in-depth against stored XSS on download).
            # Applies to ALL download routes.
            "X-Content-Type-Options": "nosniff",
        },
    )
