"""Grant consumptions search — filtered/paginated query against grant_consumptions_entry."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from datetime import datetime as _dt

from app.tools.entries.grant_consumptions.types import (
    GetGrantConsumptionResponse,
)
from app.utils.cache.hedged_row import hedged_search


async def search_grant_consumptions(
    conn: asyncpg.Connection,
    redis: Redis,
    grant_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_cache: bool = False,
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
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "grant_id": str(r["grant_id"]),
            "created_at": r["created_at"],
            "active": r["active"],
            "mcp": r["mcp"],
            "generated": r["generated"],
        }
        for r in rows
    ]

    grant_ids_str = {str(g) for g in grant_ids} if grant_ids else None

    def _parse_ts(ts):
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    def matches(row: dict) -> bool:
        if grant_ids_str is not None and str(row.get("grant_id")) not in grant_ids_str:
            return False
        ts = _parse_ts(row.get("created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        if mcp is not None and row.get("mcp") != mcp:
            return False
        return True

    merged = await hedged_search(
        redis,
        "grant_consumptions",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetGrantConsumptionResponse.model_validate(r) for r in merged]
