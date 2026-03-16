"""Emulations search — filtered/paginated query against emulations_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.emulations.types import GetEmulationResponse

MV_NAME = "emulations_mv"


async def search_emulations(
    conn: asyncpg.Connection,
    profile_ids: list[UUID] | None = None,
    grant_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetEmulationResponse]:
    """Search emulations from emulations_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT emulation_id, profile_id, grant_id, session_id, created_at, active, mcp, generated
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR profile_id = ANY($1))
          AND ($2::uuid[] IS NULL OR grant_id = ANY($2))
          AND ($3::uuid[] IS NULL OR session_id = ANY($3))
          AND ($4::timestamptz IS NULL OR created_at >= $4)
          AND ($5::timestamptz IS NULL OR created_at <= $5)
          AND ($6::boolean IS NULL OR mcp = $6)
        ORDER BY created_at DESC
        LIMIT $7 OFFSET $8
        """,
        profile_ids,
        grant_ids,
        session_ids,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetEmulationResponse(
            id=r["emulation_id"],
            profile_id=r["profile_id"],
            grant_id=r["grant_id"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
