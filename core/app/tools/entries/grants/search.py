"""Grants search — filtered/paginated query against grants_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.grants.types import GetGrantResponse

MV_NAME = "grants_mv"


async def search_grants(
    conn: asyncpg.Connection,
    session_ids: list[UUID] | None = None,
    profiles_ids: list[UUID] | None = None,
    active: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetGrantResponse]:
    """Search grants from grants_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, session_id, expires_at, created_at, active, generated, mcp, profiles_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR session_id = ANY($1))
          AND ($4::uuid[] IS NULL OR profiles_id = ANY($4))
          AND ($5::boolean IS NULL OR active = $5)
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        session_ids,
        limit,
        offset,
        profiles_ids,
        active,
    )

    return [GetGrantResponse(**dict(r)) for r in rows]
