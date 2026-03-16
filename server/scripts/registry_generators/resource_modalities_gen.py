"""Generate RESOURCE_MODALITIES from convention.

All resources default to {"call"} — resources are references/metadata,
never requiring media output modalities.
"""

from __future__ import annotations


def generate_resource_modalities(resource_keys: list[str]) -> dict[str, list[str]]:
    """Generate RESOURCE_MODALITIES — all resources are {"call"}."""
    return {key: ["call"] for key in sorted(resource_keys)}
