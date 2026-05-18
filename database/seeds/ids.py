"""Deterministic seed IDs — same input always produces the same UUID.

Usage:
    from database.seeds.ids import sid

    CONFUSED = sid("uni/persona/confused")   # always the same UUID
"""

from uuid import UUID, uuid5

# Fixed namespace — never change this or all seed IDs will shift.
SEED_NS = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def sid(key: str) -> UUID:
    """Deterministic seed ID from a human-readable key."""
    return uuid5(SEED_NS, key)
