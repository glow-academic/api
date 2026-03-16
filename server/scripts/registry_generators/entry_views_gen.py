"""Generate ENTRY_VIEW_SCHEMAS and ENTRY_VIEW_NAMES from MV introspection."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.v5.registry.manual import ENTRY_TABLE_TO_KEY

from .db import get_connection, query_rows

# Convention: entry_key → MV name
# Most follow: attempt_{singular}_mv
# Exceptions: debug_info_mv, attempt_responses_mv
_MV_NAME_OVERRIDES: dict[str, str] = {
    "debug_info": "debug_info_mv",
    "attempt_responses": "attempt_responses_mv",
}

# Singular forms for entry keys (for MV name convention)
_SINGULAR_MAP: dict[str, str] = {
    "analyses": "analysis",
    "contents": "content",
    "feedbacks": "feedback",
    "grades": "grade",
    "highlights": "highlight",
    "hints": "hint",
    "improvements": "improvement",
    "replacements": "replacement",
    "strengths": "strength",
}


def _entry_key_to_mv_name(entry_key: str) -> str:
    """Convert entry key to MV name using convention + overrides."""
    if entry_key in _MV_NAME_OVERRIDES:
        return _MV_NAME_OVERRIDES[entry_key]
    singular = _SINGULAR_MAP.get(entry_key, entry_key)
    return f"attempt_{singular}_mv"


# Query MV columns via pg_attribute (information_schema doesn't include MVs)
MV_COLUMNS_SQL = """\
SELECT
    c.relname AS mv_name,
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
WHERE c.relkind = 'm'
    AND n.nspname = 'public'
    AND a.attnum > 0
    AND NOT a.attisdropped
ORDER BY c.relname, a.attnum;
"""


def _pg_format_type_to_registry(format_type: str) -> str:
    """Convert pg_catalog.format_type output to registry type string."""
    ft = format_type.lower().strip()
    if ft == "uuid":
        return "uuid"
    if ft in ("text", "character varying"):
        return "text"
    if ft == "boolean":
        return "bool"
    if ft in ("integer", "smallint", "bigint"):
        return "int"
    if ft in ("real", "double precision"):
        return "float"
    if ft == "numeric":
        return "numeric"
    if ft.startswith("timestamp"):
        return "timestamp"
    if ft.endswith("[]"):
        return "array"
    # Anything else (user-defined enums, etc.)
    return "enum"


def generate_entry_view_schemas() -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Query DB and return (ENTRY_VIEW_SCHEMAS, ENTRY_VIEW_NAMES)."""
    # Build MV name → entry key mapping
    entry_keys = list(ENTRY_TABLE_TO_KEY.values())
    mv_to_entry: dict[str, str] = {}
    entry_to_mv: dict[str, str] = {}
    for entry_key in entry_keys:
        mv_name = _entry_key_to_mv_name(entry_key)
        mv_to_entry[mv_name] = entry_key
        entry_to_mv[entry_key] = mv_name

    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = query_rows(cur, MV_COLUMNS_SQL)
        cur.close()
    finally:
        conn.close()

    schemas: dict[str, dict[str, str]] = {}
    for mv_name, column_name, format_type in rows:
        entry_key = mv_to_entry.get(mv_name)
        if entry_key is None:
            continue
        if entry_key not in schemas:
            schemas[entry_key] = {}
        schemas[entry_key][column_name] = _pg_format_type_to_registry(format_type)

    schemas = dict(sorted(schemas.items()))
    entry_view_names = dict(sorted(entry_to_mv.items()))
    return schemas, entry_view_names
