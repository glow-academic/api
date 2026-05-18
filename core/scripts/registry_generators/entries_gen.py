"""Generate ENTRY_SCHEMAS from entry table introspection."""

from __future__ import annotations

import os
import sys

# Add server directory to path so we can import manual.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.v5.registry.manual import ENTRY_TABLE_TO_KEY

from .db import get_connection, query_rows
from .type_map import SYSTEM_COLUMNS, pg_type_to_registry


def _build_entry_columns_sql(entry_tables: list[str]) -> str:
    """Build SQL to query columns for specific entry tables."""
    table_list = ", ".join(f"'{t}'" for t in entry_tables)
    return f"""\
SELECT
    t.table_name,
    c.column_name,
    c.data_type,
    c.udt_name
FROM information_schema.tables t
JOIN information_schema.columns c
    ON t.table_name = c.table_name
    AND t.table_schema = c.table_schema
WHERE t.table_schema = 'public'
    AND t.table_name IN ({table_list})
    AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name, c.ordinal_position;
"""


def generate_entry_schemas() -> dict[str, dict[str, str]]:
    """Query DB and return ENTRY_SCHEMAS dict."""
    entry_tables = list(ENTRY_TABLE_TO_KEY.keys())
    sql = _build_entry_columns_sql(entry_tables)

    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = query_rows(cur, sql)
        cur.close()
    finally:
        conn.close()

    schemas: dict[str, dict[str, str]] = {}
    for table_name, column_name, data_type, udt_name in rows:
        if column_name in SYSTEM_COLUMNS:
            continue
        entry_key = ENTRY_TABLE_TO_KEY.get(table_name)
        if entry_key is None:
            continue
        if entry_key not in schemas:
            schemas[entry_key] = {}
        schemas[entry_key][column_name] = pg_type_to_registry(data_type, udt_name)

    return dict(sorted(schemas.items()))
