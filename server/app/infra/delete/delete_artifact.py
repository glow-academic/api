"""Shared delete helper for artifact tool functions."""

from uuid import UUID

import asyncpg


async def delete_artifacts(
    conn: asyncpg.Connection,
    *,
    table: str,
    ids: list[UUID],
    soft: bool = False,
) -> list[UUID]:
    """Delete artifacts by IDs. Returns list of affected IDs.

    soft=False (default): hard DELETE — junction FKs cascade.
    soft=True: sets active=false — data is recoverable.
    """
    if not ids:
        return []

    if soft:
        rows = await conn.fetch(
            f"UPDATE {table} SET active = false WHERE id = ANY($1) RETURNING id",
            ids,
        )
    else:
        rows = await conn.fetch(
            f"DELETE FROM {table} WHERE id = ANY($1) RETURNING id",
            ids,
        )

    return [r["id"] for r in rows]
