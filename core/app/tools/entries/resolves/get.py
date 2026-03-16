"""Resolves GET — batch get from resolves_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.resolves.types import GetResolveResponse

MV_NAME = "resolves_mv"


async def get_resolves(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetResolveResponse]:
    """Get resolves by IDs from resolves_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, problem_id, resolved, call_id
        FROM {source}
        WHERE id = ANY($1)
        """,
        ids,
    )

    return [
        GetResolveResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            problem_id=r["problem_id"],
            resolved=r["resolved"],
            call_id=r["call_id"],
        )
        for r in rows
    ]
