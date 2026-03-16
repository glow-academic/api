"""Grant consumptions search — filtered/paginated query against grant_consumptions_entry."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.grant_consumptions.types import (
    GetGrantConsumptionResponse,
)


async def search_grant_consumptions(
    conn: asyncpg.Connection,
    grant_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetGrantConsumptionResponse]:
    """Search grant consumptions with declarative filters."""
    rows = await conn.fetch(
        """
        SELECT id, grant_id, created_at, active, mcp, generated
        FROM grant_consumptions_entry
        WHERE ($1::uuid[] IS NULL OR grant_id = ANY($1))
          AND ($2::timestamptz IS NULL OR created_at >= $2)
          AND ($3::timestamptz IS NULL OR created_at <= $3)
          AND ($4::boolean IS NULL OR mcp = $4)
        ORDER BY created_at DESC
        LIMIT $5 OFFSET $6
        """,
        grant_ids,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetGrantConsumptionResponse(
            id=r["id"],
            grant_id=r["grant_id"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
