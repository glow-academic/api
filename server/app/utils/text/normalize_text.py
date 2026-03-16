"""Normalize text by removing accents and collapsing whitespace."""

import re
import unicodedata


def normalize_text(text: str | None) -> str:
    """Normalize text by removing accents, converting to lowercase, and collapsing whitespace."""
    text = text or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.strip().lower())
