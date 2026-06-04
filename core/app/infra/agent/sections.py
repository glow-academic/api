"""Canonical agent section assembly."""

from __future__ import annotations


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive a flag key/label from names like 'agent_active'."""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("agent_", "")
    label = key.replace("_", " ").title()
    return (key, label)
