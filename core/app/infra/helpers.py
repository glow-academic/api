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


def sorted_dedupe_by_id(items: list[Any], id_attr: str = "id") -> list[Any]:
    """Dedupe then sort by str(id) for stable, selection-independent ordering.

    Why: when a resource list is assembled from `suggestions + selected` (or
    vice versa), items only present in `selected` end up at the end, which
    makes them visually "jump" when the user toggles selection. Sorting by
    str(id) gives a deterministic position per item regardless of which list
    it came from. UUID v7 ids are time-ordered, so the result is effectively
    chronological.
    """
    deduped = dedupe_by_id(items, id_attr=id_attr)
    deduped.sort(key=lambda x: str(getattr(x, id_attr, "") or ""))
    return deduped
