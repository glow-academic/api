"""Shared pure-Python helpers for infra and artifact layers."""

from __future__ import annotations

from typing import Any
from uuid import UUID


def dedupe_by_id(items: list[Any], id_attr: str = "id") -> list[Any]:
    """Preserve order while deduplicating by a given attribute.

    Skips items where the attribute is None/missing.
    """
    seen: set[UUID] = set()
    output: list[Any] = []
    for item in items:
        item_id = getattr(item, id_attr, None)
        if item_id and item_id not in seen:
            seen.add(item_id)
            output.append(item)
    return output
