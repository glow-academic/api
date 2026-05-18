"""Helpers for generation resource handling."""

from __future__ import annotations

import uuid
from typing import Any


def normalize_resources_for_sql(
    resources: list[dict[str, Any]] | None,
) -> list[tuple[str, list[uuid.UUID]]] | None:
    """Normalize resources list to SQL composite-friendly tuples.

    Filters out any non-UUID resource_ids (e.g., composite IDs).
    """
    if not resources:
        return None

    normalized: list[tuple[str, list[uuid.UUID]]] = []
    for resource in resources:
        resource_type = resource.get("resource_type")
        resource_ids = resource.get("resource_ids")
        if not resource_type or not isinstance(resource_ids, list):
            continue
        uuid_ids: list[uuid.UUID] = []
        for rid in resource_ids:
            try:
                uuid_ids.append(uuid.UUID(str(rid)))
            except (ValueError, TypeError):
                continue
        if uuid_ids:
            normalized.append((str(resource_type), uuid_ids))

    return normalized or None
