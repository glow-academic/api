"""SQL constants for FK-based relation discovery.

These are used by generate_registry.py for artifact_resources and entry_resources generation.
"""

from __future__ import annotations

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
