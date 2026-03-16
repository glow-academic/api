"""Tokenize normalized text into words."""

from app.utils.text.normalize_text import normalize_text


def tokenize(text: str | None) -> list[str]:
    """Tokenize normalized text into words."""
    return [t for t in normalize_text(text).split(" ") if t]
