"""Grant consumptions CREATE — insert into grant_consumptions_entry."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.grant_consumptions.types import (
    CreateGrantConsumptionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_grant_consumption(
    conn: asyncpg.Connection,
    redis: Redis,
    grant_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateGrantConsumptionResponse:
    """Create a grant consumption entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO grant_consumptions_entry (id, grant_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id, created_at
        """,
        grant_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create grant consumption entry")

    consumption_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(consumption_id),
        "grant_id": str(grant_id),
        "created_at": created_at.isoformat(),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
    }
    await write_back_row(
        redis,
        "grant_consumptions",
        consumption_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateGrantConsumptionResponse(id=consumption_id)
