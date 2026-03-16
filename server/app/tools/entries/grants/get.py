"""grants/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.grants.types import GetGrantResponse

MV_NAME = "grants_mv"


async def get_grants(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetGrantResponse]:
    """Get grant entries by IDs from grants_mv."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT id, session_id, expires_at, created_at, active, generated, mcp, profiles_id
        FROM {MV_NAME}
        WHERE id = ANY($1)
        """,
        ids,
    )

    return [GetGrantResponse(**dict(r)) for r in rows]
