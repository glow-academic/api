"""Shared test helpers — enforces correct patterns for test data isolation."""

from uuid import UUID, uuid4


def unique_tag() -> str:
    """Short unique string for test data isolation (name suffixes, search tags)."""
    return uuid4().hex[:8]


def nonexistent_id() -> UUID:
    """UUID guaranteed not to exist in the database — for 'returns empty' tests."""
    return uuid4()
