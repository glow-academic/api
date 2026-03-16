"""Nesting helper for SQL results using __ convention.

Converts flat rows with `agent__name` to nested `{"agent": {"name": ...}}`.
"""

from collections.abc import Iterable, Mapping
from typing import Any


def nest_row(row: Mapping[str, Any], sep: str = "__") -> dict[str, Any]:
    """Convert flat row with nested keys to nested dictionary.

    Example:
        Input: {"agent__name": "Test", "agent__id": "123", "success": True}
        Output: {"agent": {"name": "Test", "id": "123"}, "success": True}

    Args:
        row: Flat row dictionary with keys like "agent__name"
        sep: Separator for nested keys (default: "__")

    Returns:
        Nested dictionary
    """
    out: dict[str, Any] = {}

    for key, value in row.items():
        if sep not in key:
            out[key] = value
            continue

        # Split on separator and build nested structure
        parts = key.split(sep)
        cur: dict[str, Any] = out

        # Navigate/create nested dictionaries
        for p in parts[:-1]:
            nxt = cur.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[p] = nxt
            cur = nxt

        # Set the final value
        cur[parts[-1]] = value

    return out


def nest(
    rows: Iterable[Mapping[str, Any]] | Mapping[str, Any],
    sep: str = "__",
) -> dict[str, Any]:
    """Universal nesting based purely on __ convention.

    Auto-detects everything from column naming patterns. No configuration needed.
    Works with single rows or multiple rows.

    Patterns:
    - prefix__key_field__field_name → dict[prefix][key_value][field_name]
    - prefix__key_field → the key value itself (indicates key field for dict)
    - prefix__field → scalar field under prefix (if no key_field pattern exists)
    - field → top-level scalar

    Example (multiple rows):
        Input rows:
            [
                {
                    "actor_name": "John",
                    "agents__agent_id": "agent-1",
                    "agents__agent_id__name": "Agent A",
                    "model_mapping__id": "model-1",
                    "model_mapping__id__name": "GPT-4"
                },
                {
                    "actor_name": "John",
                    "agents__agent_id": "agent-2",
                    "agents__agent_id__name": "Agent B",
                    "model_mapping__id": "model-2",
                    "model_mapping__id__name": "Claude"
                }
            ]
        Output:
            {
                "actor_name": "John",
                "agents": {
                    "agent-1": {"agent_id": "agent-1", "name": "Agent A"},
                    "agent-2": {"agent_id": "agent-2", "name": "Agent B"}
                },
                "model_mapping": {
                    "model-1": {"id": "model-1", "name": "GPT-4"},
                    "model-2": {"id": "model-2", "name": "Claude"}
                }
            }

    Example (single row):
        Input: {"agent__name": "Test", "agent__id": "123", "success": True}
        Output: {"agent": {"name": "Test", "id": "123"}, "success": True}

    Args:
        rows: Single row dictionary or iterable of row dictionaries
        sep: Separator for nested keys (default: "__")

    Returns:
        Nested dictionary with dicts for collections, scalars for top-level fields
    """
    # Handle single row case - just use nest_row
    if isinstance(rows, Mapping):
        return nest_row(rows, sep=sep)

    # Handle multiple rows - aggregate into dicts
    rows_list = list(rows)
    if not rows_list:
        return {}

    # Step 1: Parse all column names to detect structure
    column_info: dict[str, dict[str, Any]] = {}
    all_column_names: set[str] = set()

    # Collect all column names from all rows
    for row in rows_list:
        all_column_names.update(row.keys())

    for col_name in all_column_names:
        if col_name in column_info:
            continue  # Already parsed

        parts = col_name.split(sep)

        if len(parts) == 1:
            # Top-level scalar: "actor_name"
            column_info[col_name] = {"type": "scalar", "path": [], "field": parts[0]}

        elif len(parts) == 2:
            # prefix__field: Could be key field or scalar field
            prefix = parts[0]
            field = parts[1]

            # Check if this is a key field (prefix__key_field pattern)
            # We'll determine this by checking if there are prefix__key_field__field_name columns
            has_nested_fields = any(
                other_col.startswith(f"{prefix}__{field}__")
                for other_col in all_column_names
            )

            if has_nested_fields:
                # This is a key field: prefix__key_field
                column_info[col_name] = {
                    "type": "key_field",
                    "prefix": prefix,
                    "key_field": field,
                }
            else:
                # This is a scalar field: prefix__field
                column_info[col_name] = {
                    "type": "scalar_field",
                    "prefix": prefix,
                    "field": field,
                }

        elif len(parts) >= 3:
            # prefix__key_field__field_name or nested: prefix__key1__key2__field
            prefix = parts[0]
            key_field = parts[1]
            field = parts[-1]
            key_path = parts[1:-1]  # All middle parts

            column_info[col_name] = {
                "type": "dict_item",
                "prefix": prefix,
                "key_field": key_field,
                "key_path": key_path,
                "field": field,
            }

    # Step 2: Build result structure
    result: dict[str, Any] = {}

    # Collect all prefixes that should become dicts
    dict_prefixes: dict[str, str] = {}  # prefix -> key_field

    for col_name, info in column_info.items():
        if info["type"] == "key_field":
            prefix = info["prefix"]
            key_field = info["key_field"]
            dict_prefixes[prefix] = key_field

    # Step 3: Process top-level scalars
    for col_name, info in column_info.items():
        if info["type"] == "scalar":
            # Use value from first row (all rows should have same value)
            result[info["field"]] = rows_list[0].get(col_name)

    # Step 4: Process dict collections
    for prefix, key_field in dict_prefixes.items():
        collection: dict[str, Any] = {}

        for row in rows_list:
            # Get the key value from prefix__key_field column
            key_col = f"{prefix}__{key_field}"
            key_value = row.get(key_col)

            if key_value is None:
                continue

            key_str = str(key_value)

            # Initialize dict entry if not seen
            if key_str not in collection:
                collection[key_str] = {key_field: key_value}

            # Build a temporary row with just this prefix's columns (relative to prefix__key_field)
            temp_row: dict[str, Any] = {}
            for col_name, value in row.items():
                if col_name.startswith(f"{prefix}__{key_field}__"):
                    # Remove prefix__key_field__ to get relative path
                    relative_path = col_name[len(f"{prefix}__{key_field}__") :]
                    temp_row[relative_path] = value
                elif col_name == f"{prefix}__{key_field}":
                    # Skip the key field itself (already set)
                    continue

            # Use nest_row to create nested structure from relative paths
            if temp_row:
                nested_item = nest_row(temp_row, sep=sep)
                # Merge nested_item into collection[key_str]
                for nested_key, nested_value in nested_item.items():
                    if nested_key != key_field:  # Don't overwrite the key field
                        collection[key_str][nested_key] = nested_value

        # Always add the prefix to result, even if empty (for API response validation)
        result[prefix] = collection

    # Step 5: Process scalar fields under prefixes (prefix__field without key_field pattern)
    for col_name, info in column_info.items():
        if info["type"] == "scalar_field":
            prefix = info["prefix"]
            field = info["field"]

            # Only add if prefix is not already a dict collection
            if prefix not in result:
                result[prefix] = {}

            if isinstance(result[prefix], dict) and prefix not in dict_prefixes:
                # Use value from first row
                result[prefix][field] = rows_list[0].get(col_name)

    return result
