"""Sanitize AI model function call kwargs.

Models (especially gpt-4.1) make predictable mistakes:
  - Pass empty strings for optional fields they don't want to set
  - Pass single strings where arrays are expected
  - Pass string "True"/"False" instead of booleans
  - Hallucinate IDs by reusing a UUID from another field
  - Pass both a value and an _id for the same resource

This module provides a reusable sanitizer that each infra function
configures for its own field types.
"""

from __future__ import annotations

from typing import Any


def sanitize_model_kwargs(
    kwargs: dict[str, Any],
    *,
    list_fields: set[str] | None = None,
    bool_fields: set[str] | None = None,
    value_id_pairs: list[tuple[str, str]] | None = None,
    drop_false_bools: set[str] | None = None,
) -> dict[str, Any]:
    """Clean up kwargs from an AI model's function call.

    Args:
        kwargs: Raw kwargs from the model (already rendered from Jinja).
        list_fields: Field names that should be lists. Single strings
            are wrapped in a list automatically.
        bool_fields: Field names that should be booleans. String
            "true"/"false" values are coerced.
        value_id_pairs: List of (value_field, id_field) tuples. If the
            model sends both, the id is dropped — models hallucinate IDs
            by reusing UUIDs from other fields.
        drop_false_bools: Boolean field names where False means "not set"
            and should be removed entirely.

    Returns:
        Cleaned kwargs dict (new dict, does not mutate input).
    """
    result = {k: v for k, v in kwargs.items() if v not in ("", None)}

    # Auto-coerce string booleans (Jinja renders booleans as "True"/"False")
    for key, val in list(result.items()):
        if isinstance(val, str) and val.lower() in ("true", "false"):
            result[key] = val.lower() == "true"

    # Explicit bool field coercion (for "1"/"yes" etc.)
    if bool_fields:
        for key in bool_fields:
            if key in result and isinstance(result[key], str):
                result[key] = result[key].lower() in ("true", "1", "yes")

    # Drop False booleans that mean "not set"
    if drop_false_bools:
        for key in drop_false_bools:
            if result.get(key) is False:
                result.pop(key, None)

    # Coerce single strings to lists
    if list_fields:
        for key in list_fields:
            if key in result and isinstance(result[key], str):
                result[key] = [result[key]]

    # If both value and _id are provided, prefer value (drop hallucinated ID)
    if value_id_pairs:
        for value_key, id_key in value_id_pairs:
            if value_key in result and id_key in result:
                del result[id_key]

    return result
