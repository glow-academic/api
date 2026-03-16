"""Generate ARTIFACT_FLAGS from DB introspection of *_flags_junction tables."""

from __future__ import annotations

from .db import get_connection

ARTIFACT_FLAGS_SIMPLE_SQL = """\
WITH flag_junctions AS (
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
        AND table_name LIKE '%%\\_flags\\_junction'
        AND table_name NOT LIKE '%%drafts%%'
        AND table_type = 'BASE TABLE'
)
SELECT
    replace(fj.table_name, '_flags_junction', '') AS artifact
FROM flag_junctions fj
ORDER BY artifact;
"""


def generate_artifact_flags() -> dict[str, list[str]]:
    """Query distinct flag names per artifact from *_flags_junction tables."""
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Find all flag junction tables
        cur.execute(ARTIFACT_FLAGS_SIMPLE_SQL)
        artifacts = [row[0] for row in cur.fetchall()]

        result: dict[str, list[str]] = {}
        for artifact in artifacts:
            junction_table = f"{artifact}_flags_junction"
            try:
                cur.execute(
                    f"SELECT DISTINCT f.name FROM {junction_table} j "
                    f"JOIN flags_resource f ON j.flags_id = f.id "
                    f"WHERE f.active = true ORDER BY f.name"
                )
                flags = [row[0] for row in cur.fetchall()]
                if flags:
                    result[artifact] = flags
            except Exception:
                pass  # Junction table might not exist or have different structure

        cur.close()
    finally:
        conn.close()

    return dict(sorted(result.items()))
