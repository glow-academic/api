"""Problems GET — batch get from problems_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.problems.types import GetProblemResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "problems_mv"


async def get_problems(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetProblemResponse]:
    """Get problems by IDs from problems_mv."""
    if not ids:
        return []

    cached_results: dict[str, GetProblemResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for pid in ids:
            cached = await read_back_row(redis, "problems", pid)
            if cached is not None:
                cached_results[str(pid)] = GetProblemResponse.model_validate(cached)
            else:
                missing_ids.append(pid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetProblemResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        source_alias = "mv" if bypass_mv else "p"
        from_source = source if bypass_mv else f"{source} {source_alias}"

        rows = await conn.fetch(
            f"""
            SELECT {source_alias}.problem_id, {source_alias}.profile_id, c.session_id, {source_alias}.type, {source_alias}.message, {source_alias}.resolved, {source_alias}.created_at, {source_alias}.active, {source_alias}.mcp, {source_alias}.generated, {source_alias}.artifact_type
            FROM {from_source}
            JOIN problems_entry pe ON pe.id = {source_alias}.problem_id
            LEFT JOIN calls_entry c ON c.id = pe.call_id
            WHERE {source_alias}.problem_id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["problem_id"])] = GetProblemResponse(
                id=r["problem_id"],
                profile_id=r["profile_id"],
                session_id=r["session_id"],
                type=r["type"],
                message=r["message"],
                resolved=r["resolved"],
                created_at=r["created_at"],
                active=r["active"],
                mcp=r["mcp"],
                generated=r["generated"],
                artifact_type=r["artifact_type"],
            )

    out: list[GetProblemResponse] = []
    for pid in ids:
        key = str(pid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
