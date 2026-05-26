"""Calls GET — batch get from calls_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.calls.types import GetCallResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "calls_mv"


async def get_calls(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetCallResponse]:
    """Get calls by IDs from calls_mv (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetCallResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for cid in ids:
            cached = await read_back_row(redis, "calls", cid)
            if cached is not None:
                cached_results[str(cid)] = GetCallResponse.model_validate(cached)
            else:
                missing_ids.append(cid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetCallResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        rows = await conn.fetch(
            f"""
            SELECT call_id, run_id, call_created_at,
                   upload_id, file_path, mime_type, tool_id
            FROM {source}
            WHERE call_id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["call_id"])] = GetCallResponse(
                id=r["call_id"],
                run_id=r["run_id"],
                created_at=r["call_created_at"],
                upload_id=r["upload_id"],
                file_path=r["file_path"],
                mime_type=r["mime_type"],
                tool_id=r["tool_id"],
            )

    out: list[GetCallResponse] = []
    for cid in ids:
        key = str(cid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
