"""Personas GET — read from base table + connection table."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.personas.types import GetPersonasResponse


async def get_personas(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetPersonasResponse]:
    """Get personas entries by IDs with their persona connections."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            e.id, e.created_at, e.active, e.generated, e.mcp, e.session_id,
            COALESCE(ARRAY_AGG(DISTINCT pc.personas_id) FILTER (WHERE pc.personas_id IS NOT NULL), '{}') AS persona_ids
        FROM personas_entry e
        LEFT JOIN personas_personas_connection pc ON pc.personas_entry_id = e.id
        WHERE e.id = ANY($1) AND e.active = true
        GROUP BY e.id, e.created_at, e.active, e.generated, e.mcp, e.session_id
        ORDER BY e.created_at DESC
        """,
        ids,
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
