"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.grant_consumptions.types import (
    GetGrantConsumptionResponse,
)

MV_NAME = "grant_consumptions_mv"


async def get_grant_consumptions(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetGrantConsumptionResponse]:
    """Get grant consumption entries by IDs from grant_consumptions_mv."""
    if not ids:
        return []

    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", ids)

    return [GetGrantConsumptionResponse(**dict(r)) for r in rows]
