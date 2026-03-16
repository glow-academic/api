"""Grant consumptions CREATE — insert into grant_consumptions_entry."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.grant_consumptions.types import (
    CreateGrantConsumptionResponse,
)


async def create_grant_consumption(
    conn: asyncpg.Connection,
    grant_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateGrantConsumptionResponse:
    """Create a grant consumption entry."""
    consumption_id = await conn.fetchval(
        """
        INSERT INTO grant_consumptions_entry (id, grant_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id
        """,
        grant_id,
        not soft,
        mcp,
        id,
    )

    if consumption_id is None:
        raise ValueError("Failed to create grant consumption entry")

    return CreateGrantConsumptionResponse(id=consumption_id)
