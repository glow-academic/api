"""artifact_resources_relation (artifact_type → resource_type)."""

from __future__ import annotations

ARTIFACT_RESOURCES: dict[str, frozenset[str]] = {
    "agent": frozenset(
        {
            "agents",
            "departments",
            "descriptions",
            "flags",
            "instructions",
        }
    ),
}
