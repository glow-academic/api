"""Tests for app.utils.text.tokenize."""

from app.utils.text.tokenize import tokenize


def test_basic_tokenization():
    """Simple sentence splits into words."""
    assert tokenize("Hello World") == ["hello", "world"]


def test_extra_whitespace_collapsed():
    """Extra whitespace does not produce empty tokens."""
    assert tokenize("  one   two  ") == ["one", "two"]


def test_none_returns_empty_list():
    """None input yields empty list."""
    assert tokenize(None) == []


def test_empty_string_returns_empty_list():
    """Empty string yields empty list."""
    assert tokenize("") == []


def test_accents_removed_during_tokenize():
    """Accented characters are normalized before splitting."""
    assert tokenize("\u00c9cole Fran\u00e7aise") == ["ecole", "francaise"]


def test_single_word():
    """Single word returns list with one element."""
    assert tokenize("hello") == ["hello"]
