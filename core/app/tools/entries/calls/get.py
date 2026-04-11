"""Calls GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.calls.types import GetCallResponse

MV_NAME = "calls_mv"


async def get_calls(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetCallResponse]:
    """Get calls entries by IDs from calls_mv."""
    if not ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE call_id = ANY($1)",
        ids,
    )
    return [GetCallResponse(**dict(r)) for r in rows]


async def get_call(
    conn: asyncpg.Connection,
    call_id: UUID,
) -> GetCallResponse | None:
    """Get a single call by ID from calls_mv."""
    items = await get_calls(conn, [call_id])
    return items[0] if items else None
