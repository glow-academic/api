"""Tokens GET — batch get from tokens_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.tokens.types import GetTokenResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "tokens_mv"


async def get_tokens(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetTokenResponse]:
    """Get tokens by IDs from tokens_mv (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetTokenResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for tid in ids:
            cached = await read_back_row(redis, "tokens", tid)
            if cached is not None:
                cached_results[str(tid)] = GetTokenResponse.model_validate(cached)
            else:
                missing_ids.append(tid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetTokenResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        rows = await conn.fetch(
            f"""
            SELECT id, created_at, generated, mcp, active, run_id,
                   input_tokens, output_tokens, cached_input_tokens, session_id
            FROM {source}
            WHERE id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetTokenResponse(
                id=r["id"],
                created_at=r["created_at"],
                generated=r["generated"],
                mcp=r["mcp"],
                active=r["active"],
                run_id=r["run_id"],
                input_tokens=r["input_tokens"],
                output_tokens=r["output_tokens"],
                cached_input_tokens=r["cached_input_tokens"],
                session_id=r["session_id"],
            )

    out: list[GetTokenResponse] = []
    for tid in ids:
        key = str(tid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
