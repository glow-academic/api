"""Tokens search — filtered/paginated query against tokens_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.tokens.types import GetTokenResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "tokens_mv"


def _parse_ts(ts):
    if isinstance(ts, str):
        return datetime.fromisoformat(ts)
    return ts


async def search_tokens(
    conn: asyncpg.Connection,
    redis: Redis,
    run_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetTokenResponse]:
    """Search tokens from tokens_mv with declarative filters (with cache hedge)."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, run_id,
               input_tokens, output_tokens, cached_input_tokens, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR run_id = ANY($1))
          AND ($2::uuid[] IS NULL OR session_id = ANY($2))
          AND ($3::timestamptz IS NULL OR created_at >= $3)
          AND ($4::timestamptz IS NULL OR created_at <= $4)
          AND ($5::boolean IS NULL OR mcp = $5)
        ORDER BY created_at DESC
        LIMIT $6 OFFSET $7
        """,
        run_ids,
        session_ids,
        date_from,
        date_to,
        mcp,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "created_at": r["created_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
            "run_id": str(r["run_id"]) if r["run_id"] else None,
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "cached_input_tokens": r["cached_input_tokens"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
        }
        for r in rows
    ]

    run_ids_str = {str(r) for r in run_ids} if run_ids else None
    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def matches(row: dict) -> bool:
        if run_ids_str is not None and str(row.get("run_id")) not in run_ids_str:
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        if mcp is not None and bool(row.get("mcp")) != mcp:
            return False
        ts = _parse_ts(row.get("created_at"))
        if ts is None:
            return False
        if date_from is not None and ts < date_from:
            return False
        if date_to is not None and ts > date_to:
            return False
        return True

    merged = await hedged_search(
        redis,
        "tokens",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetTokenResponse.model_validate(r) for r in merged]
