"""
Generate registry relation dicts from database FK relationships.

Derives 3 of the 10 dicts in server/app/registry/relations.py:
  - ARTIFACT_RESOURCES  (artifact_type → resource_type)
  - ENTRY_RESOURCES     (entry_type → resource_type)
  - RESOURCE_ENTRIES    (resource_type → entry_type)  [inverse of ENTRY_RESOURCES]

Usage:
    python server/scripts/generate_registry_relations.py
"""

from __future__ import annotations

import os
from collections import defaultdict

import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "mydb")
DB_USER = os.environ.get("DB_USER", "myuser")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "mypassword")

ARTIFACT_RESOURCES_SQL = """\
WITH junction_fks AS (
    SELECT tc.table_name AS junction,
           ccu.table_name AS referenced
    FROM information_schema.table_constraints tc
    JOIN information_schema.constraint_column_usage ccu
      ON tc.constraint_name = ccu.constraint_name
      AND tc.table_schema = ccu.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND tc.table_name LIKE '%%\\_junction'
      AND tc.table_name NOT LIKE '%%drafts%%'
      AND tc.table_name NOT LIKE '%%calls%%'
),
artifact_side AS (
    SELECT junction, replace(referenced, '_artifact', '') AS artifact
    FROM junction_fks WHERE referenced LIKE '%%_artifact'
),
resource_side AS (
    SELECT junction, replace(referenced, '_resource', '') AS resource
    FROM junction_fks WHERE referenced LIKE '%%_resource'
)
SELECT a.artifact, r.resource
FROM artifact_side a
JOIN resource_side r ON a.junction = r.junction
ORDER BY a.artifact, r.resource;
"""

ENTRY_RESOURCES_SQL = """\
WITH connection_fks AS (
    SELECT tc.table_name AS connection,
           ccu.table_name AS referenced
    FROM information_schema.table_constraints tc
    JOIN information_schema.constraint_column_usage ccu
      ON tc.constraint_name = ccu.constraint_name
      AND tc.table_schema = ccu.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND tc.table_name LIKE '%%\\_connection'
      AND tc.table_name NOT LIKE '%%drafts%%'
      AND tc.table_name NOT LIKE '%%resolved%%'
      AND tc.table_name NOT LIKE '%%calls%%'
),
entry_side AS (
    SELECT connection, replace(referenced, '_entry', '') AS entry
    FROM connection_fks WHERE referenced LIKE '%%_entry'
),
resource_side AS (
    SELECT connection, replace(referenced, '_resource', '') AS resource
    FROM connection_fks WHERE referenced LIKE '%%_resource'
)
SELECT e.entry, r.resource
FROM entry_side e
JOIN resource_side r ON e.connection = r.connection
ORDER BY e.entry, r.resource;
"""


def query_rows(cur, sql: str) -> list[tuple[str, str]]:
    cur.execute(sql)
    return cur.fetchall()


def group_by_key(rows: list[tuple[str, str]]) -> dict[str, sorted]:
    result: dict[str, set[str]] = defaultdict(set)
    for key, value in rows:
        result[key].add(value)
    return {k: sorted(v) for k, v in sorted(result.items())}


def invert_map(grouped: dict[str, list[str]]) -> dict[str, list[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for key, values in grouped.items():
        for v in values:
            result[v].add(key)
    return {k: sorted(v) for k, v in sorted(result.items())}


def format_frozenset(values: list[str], indent: int = 8) -> str:
    pad = " " * indent
    if len(values) <= 2:
        items = ", ".join(f'"{v}"' for v in values)
        return f"frozenset({{{items}}})"
    lines = [f'{pad}"{v}",' for v in values]
    return (
        "frozenset(\n"
        + " " * (indent)
        + "{\n"
        + "\n".join(lines)
        + "\n"
        + " " * indent
        + "}\n"
        + " " * (indent - 4)
        + ")"
    )


def format_dict(name: str, type_hint: str, grouped: dict[str, list[str]]) -> str:
    lines = [f"# {name}"]
    lines.append(f"{name.upper().replace(' ', '_').split(' ')[0]}: {type_hint} = {{")

    # Use the actual variable name from the type hint context
    # Just format the dict entries
    items = []
    for key, values in sorted(grouped.items()):
        items.append(format_entry(key, values))

    lines_str = lines[0] + "\n" + lines[1]
    # Actually let me redo this more cleanly
    return _format_dict_clean(name, type_hint, grouped)


def _format_dict_clean(
    comment: str, type_hint: str, grouped: dict[str, list[str]]
) -> str:
    var_name = comment.upper()
    parts = [f"# {comment}"]
    parts.append(f"{var_name}: {type_hint} = {{")

    for key, values in sorted(grouped.items()):
        if len(values) <= 3:
            items_str = ", ".join(f'"{v}"' for v in values)
            parts.append(f'    "{key}": frozenset({{{items_str}}}),')
        else:
            parts.append(f'    "{key}": frozenset(')
            parts.append("        {")
            for v in values:
                parts.append(f'            "{v}",')
            parts.append("        }")
            parts.append("    ),")

    parts.append("}")
    return "\n".join(parts)


def format_entry(key: str, values: list[str]) -> str:
    # unused, kept for compat
    return ""


def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    try:
        cur = conn.cursor()

        # ARTIFACT_RESOURCES
        ar_rows = query_rows(cur, ARTIFACT_RESOURCES_SQL)
        ar_grouped = group_by_key(ar_rows)

        # ENTRY_RESOURCES
        er_rows = query_rows(cur, ENTRY_RESOURCES_SQL)
        er_grouped = group_by_key(er_rows)

        # RESOURCE_ENTRIES (inverse of ENTRY_RESOURCES)
        re_grouped = invert_map(er_grouped)

        cur.close()
    finally:
        conn.close()

    type_hint = "dict[str, frozenset[str]]"

    print(
        _format_dict_clean(
            "ARTIFACT_RESOURCES",
            type_hint,
            ar_grouped,
        )
    )
    print()
    print(
        _format_dict_clean(
            "ENTRY_RESOURCES",
            type_hint,
            er_grouped,
        )
    )
    print()
    print(
        _format_dict_clean(
            "RESOURCE_ENTRIES",
            type_hint,
            re_grouped,
        )
    )


if __name__ == "__main__":
    main()
