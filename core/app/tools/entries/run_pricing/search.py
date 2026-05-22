"""Run pricing search — filtered/paginated query against run_pricing_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.run_pricing.types import GetRunPricingResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "run_pricing_mv"


async def search_run_pricing_entries_internal(
    conn: asyncpg.Connection,
    redis: Redis,
    run_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
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
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "pricing_type": r["pricing_type"],
            "count": r["count"],
            "run_id": str(r["run_id"]) if r["run_id"] else None,
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "created_at": r["created_at"],
            "active": r["active"],
            "mcp": r["mcp"],
            "generated": r["generated"],
        }
        for r in rows
    ]

    run_ids_str = {str(r) for r in run_ids} if run_ids else None

    def matches(row: dict) -> bool:
        if run_ids_str is not None and str(row.get("run_id")) not in run_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "run_pricing",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetRunPricingResponse.model_validate(r) for r in merged]
