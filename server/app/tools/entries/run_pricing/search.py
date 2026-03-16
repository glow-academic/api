"""Run pricing search — filtered/paginated query against run_pricing_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.run_pricing.types import GetRunPricingResponse

MV_NAME = "run_pricing_mv"


async def search_run_pricing_entries_internal(
    conn: asyncpg.Connection,
    run_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetRunPricingResponse]:
    """Search run_pricing entries from run_pricing_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, pricing_type, count, run_id, session_id,
               created_at, active, mcp, generated
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR run_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        run_ids,
        limit,
        offset,
    )

    return [GetRunPricingResponse(**dict(r)) for r in rows]
