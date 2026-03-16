"""Shared activate helper for artifact/resource/entry tool functions."""

from uuid import UUID

import asyncpg


async def activate_rows(
    conn: asyncpg.Connection,
    *,
    table: str,
    ids: list[UUID],
) -> list[UUID]:
    """Activate rows by IDs. Returns list of affected IDs.

    Sets active=true on the given rows. This is the inverse of soft delete
    and the "upgrade" path for soft-created artifacts/resources/entries.
    """
    if not ids:
        return []

    rows = await conn.fetch(
        f"UPDATE {table} SET active = true WHERE id = ANY($1) RETURNING id",
        ids,
    )

    return [r["id"] for r in rows]
