"""Get best-effort content type for a file."""

from app.utils.mime.infer_mime_from_name import DEFAULT_FALLBACK, infer_mime_from_name


def get_content_type(filename: str, mime_type: str | None = None) -> str:
    """
    Best-effort content type:
      - Trust stored mime if it isn't generic.
      - Otherwise infer from name (mimetypes -> override map -> fallback).
    """
    if mime_type and mime_type.lower() != "application/octet-stream":
        return mime_type
    return infer_mime_from_name(filename, fallback=DEFAULT_FALLBACK)
