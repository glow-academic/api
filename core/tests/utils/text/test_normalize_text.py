"""Tests for app.utils.text.normalize_text."""

from app.utils.text.normalize_text import normalize_text


def test_lowercases_text():
    """Text is converted to lowercase."""
    assert normalize_text("Hello WORLD") == "hello world"


def test_collapses_whitespace():
    """Multiple spaces, tabs, newlines collapse to single space."""
    assert normalize_text("hello   world\t\tfoo\n\nbar") == "hello world foo bar"


def test_strips_leading_trailing_whitespace():
    """Leading and trailing whitespace is removed."""
    assert normalize_text("  hello  ") == "hello"


def test_removes_accents():
    """Accented characters are reduced to base form."""
    assert normalize_text("\u00e9\u00e0\u00fc\u00f1") == "eaun"


def test_none_returns_empty_string():
    """None input produces empty string."""
    assert normalize_text(None) == ""


def test_empty_string_returns_empty():
    """Empty string returns empty."""
    assert normalize_text("") == ""


def test_unicode_combining_marks_removed():
    """Combining diacritical marks are stripped."""
    # "e" + combining acute accent
    assert normalize_text("e\u0301") == "e"
