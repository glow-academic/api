"""Shared SQL-builder helpers for artifact search functions.

Each artifact has its own search.py with explicit params.
These helpers build common SQL fragments (junction filters, text search).
"""

from uuid import UUID

import asyncpg


def add_junction_filter(
    conditions: list[str],
    params: list[object],
    idx: int,
    *,
    junction_table: str,
    owner_col: str,
    resource_col: str,
    ids: list[UUID],
    alias: str = "a",
) -> int:
    """Append an EXISTS filter for a junction table. Returns next param index."""
    conditions.append(
        f"EXISTS ("
        f"SELECT 1 FROM {junction_table} j "
        f"WHERE j.{owner_col} = {alias}.id AND j.active = true "
        f"AND j.{resource_col} = ANY(${idx})"
        f")"
    )
    params.append(ids)
    return idx + 1


def add_text_search(
    conditions: list[str],
    params: list[object],
    idx: int,
    *,
    junction_table: str,
    owner_col: str,
    resource_col: str,
    resource_table: str,
    text_col: str,
    search: str,
    alias: str = "a",
) -> int:
    """Append a text ILIKE filter through a junction → resource table. Returns next param index."""
    conditions.append(
        f"EXISTS ("
        f"SELECT 1 FROM {junction_table} j "
        f"JOIN {resource_table} r ON r.id = j.{resource_col} "
        f"WHERE j.{owner_col} = {alias}.id AND j.active = true "
        f"AND LOWER(r.{text_col}) LIKE '%%' || LOWER(${idx}) || '%%'"
        f")"
    )
    params.append(search)
    return idx + 1


async def execute_artifact_search(
    conn: asyncpg.Connection,
    *,
    table: str,
    conditions: list[str],
    params: list[object],
    idx: int,
    order_join: str | None = None,
    order_expr: str = "a.created_at DESC",
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Execute the final search query and return (matching artifact IDs, total_count)."""
    if limit_count <= 0:
        return ([], 0)

    where = " AND ".join(conditions) if conditions else "true"

    query = f"""
        SELECT a.id, COUNT(*) OVER() AS total_count
        FROM {table} a
        {order_join or ""}
        WHERE {where}
        GROUP BY a.id
        ORDER BY {order_expr}
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    params.extend([limit_count, offset_count])

    rows = await conn.fetch(query, *params)
    ids = [row["id"] for row in rows]
    total_count = rows[0]["total_count"] if rows else 0
    return (ids, total_count)
