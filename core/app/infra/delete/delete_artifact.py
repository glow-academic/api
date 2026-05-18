"""Shared delete/restore helpers for artifact tool functions."""

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
    soft=True: sets active=false — data is recoverable via restore_artifacts.
    """
    if not ids:
        return []

    if soft:
        # Bump ``updated_at`` so list views sorted by recency surface
        # the just-soft-deleted row as a pending action — same UX
        # treatment pending creates and updates already get from their
        # own NOW() touches.
        rows = await conn.fetch(
            f"UPDATE {table} SET active = false, updated_at = NOW() "
            f"WHERE id = ANY($1) RETURNING id",
            ids,
        )
    else:
        rows = await conn.fetch(
            f"DELETE FROM {table} WHERE id = ANY($1) RETURNING id",
            ids,
        )

    return [r["id"] for r in rows]


async def restore_artifacts(
    conn: asyncpg.Connection,
    *,
    table: str,
    ids: list[UUID],
) -> list[UUID]:
    """Restore soft-deleted artifacts by setting active=true.

    Inverse of delete_artifacts(soft=True). Returns list of restored IDs.
    """
    if not ids:
        return []

    rows = await conn.fetch(
        f"UPDATE {table} SET active = true, updated_at = NOW() "
        f"WHERE id = ANY($1) AND active = false RETURNING id",
        ids,
    )

    return [r["id"] for r in rows]
