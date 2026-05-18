"""Personas SEARCH — declarative filters on base table + connection."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.personas.types import GetPersonasResponse


async def search_personas(
    conn: asyncpg.Connection,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetPersonasResponse]:
    """Search personas entries with declarative filters."""
    rows = await conn.fetch(
        """
        SELECT
            e.id, e.created_at, e.active, e.generated, e.mcp, e.session_id,
            COALESCE(ARRAY_AGG(DISTINCT pc.personas_id) FILTER (WHERE pc.personas_id IS NOT NULL), '{}') AS persona_ids
        FROM personas_entry e
        LEFT JOIN personas_personas_connection pc ON pc.personas_entry_id = e.id
        WHERE e.active = true
          AND ($1::uuid[] IS NULL OR e.session_id = ANY($1))
          AND ($2::timestamptz IS NULL OR e.created_at >= $2)
          AND ($3::timestamptz IS NULL OR e.created_at <= $3)
        GROUP BY e.id, e.created_at, e.active, e.generated, e.mcp, e.session_id
        ORDER BY e.created_at DESC
        LIMIT $4 OFFSET $5
        """,
        session_ids,
        date_from,
        date_to,
        limit,
        offset,
    )

    return [
        GetPersonasResponse(
            id=r["id"],
            created_at=r["created_at"],
            active=r["active"],
            generated=r["generated"],
            mcp=r["mcp"],
            session_id=r["session_id"],
            persona_ids=r["persona_ids"],
        )
        for r in rows
    ]
