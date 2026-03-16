"""Generate RESOURCE_SCHEMAS from *_resource table introspection."""

from __future__ import annotations

from .db import get_connection, query_rows
from .type_map import SYSTEM_COLUMNS, pg_type_to_registry

# Query all *_resource tables and their columns
RESOURCE_COLUMNS_SQL = """\
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
    AND t.table_name LIKE '%%\\_resource'
    AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name, c.ordinal_position;
"""


def generate_resource_schemas() -> dict[str, dict[str, str]]:
    """Query DB and return RESOURCE_SCHEMAS dict."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = query_rows(cur, RESOURCE_COLUMNS_SQL)
        cur.close()
    finally:
        conn.close()

    schemas: dict[str, dict[str, str]] = {}
    for table_name, column_name, data_type, udt_name in rows:
        if column_name in SYSTEM_COLUMNS:
            continue
        # Convert table name: e.g. "names_resource" → "names"
        resource_key = table_name.replace("_resource", "")
        if resource_key not in schemas:
            schemas[resource_key] = {}
        schemas[resource_key][column_name] = pg_type_to_registry(data_type, udt_name)

    return dict(sorted(schemas.items()))
