"""Tests for app.utils.mime.infer_mime_from_name."""

from app.utils.mime.infer_mime_from_name import DEFAULT_FALLBACK, infer_mime_from_name


def test_known_extension_pdf():
    """PDF extension is correctly identified."""
    assert infer_mime_from_name("report.pdf") == "application/pdf"


def test_known_extension_png():
    """PNG extension is correctly identified."""
    assert infer_mime_from_name("photo.png") == "image/png"


def test_empty_filename_returns_fallback():
    """Empty filename returns the default fallback."""
    assert infer_mime_from_name("") == DEFAULT_FALLBACK


def test_no_extension_returns_fallback():
    """A filename without an extension returns the fallback."""
    assert infer_mime_from_name("README") == DEFAULT_FALLBACK


def test_unknown_extension_returns_fallback():
    """An unrecognized extension returns the fallback."""
    result = infer_mime_from_name("data.zzz999")
    assert result == DEFAULT_FALLBACK


def test_custom_fallback():
    """A custom fallback string is returned for unknown extensions."""
    result = infer_mime_from_name("file.unknown", fallback="text/plain")
    assert result == "text/plain"


def test_case_insensitive_matching():
    """Extension matching works regardless of case."""
    result = infer_mime_from_name("IMAGE.PNG")
    assert result == "image/png"
