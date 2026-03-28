"""Tests for app.utils.mime.get_content_type."""

from app.utils.mime.get_content_type import get_content_type


def test_trusts_stored_mime_when_specific():
    """If a non-generic MIME type is provided, it is returned as-is."""
    assert get_content_type("photo.jpg", mime_type="image/jpeg") == "image/jpeg"


def test_ignores_octet_stream_and_infers():
    """application/octet-stream is generic; function should infer from filename."""
    result = get_content_type("doc.pdf", mime_type="application/octet-stream")
    assert result == "application/pdf"


def test_infers_from_filename_when_mime_is_none():
    """When mime_type is None, infer from the filename."""
    result = get_content_type("image.png")
    assert result == "image/png"


def test_fallback_for_unknown_extension():
    """Unknown extensions should fall back to application/octet-stream."""
    result = get_content_type("data.xyz123")
    assert result == "application/octet-stream"


def test_empty_filename_with_none_mime():
    """Empty filename with no stored mime gives fallback."""
    result = get_content_type("")
    assert result == "application/octet-stream"
