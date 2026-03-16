"""Emulations GET — batch get from emulations_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.emulations.types import GetEmulationResponse

MV_NAME = "emulations_mv"


async def get_emulations(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetEmulationResponse]:
    """Get emulations by IDs from emulations_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT emulation_id, profile_id, grant_id, session_id, created_at, active, mcp, generated
        FROM {source}
        WHERE emulation_id = ANY($1)
        """,
        ids,
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
