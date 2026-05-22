"""Problems search — filtered/paginated query against problems_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from datetime import datetime as _dt

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.problems.types import GetProblemResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "problems_mv"


async def search_problems(
    conn: asyncpg.Connection,
    redis: Redis,
    profile_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    type: str | None = None,
    resolved: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    artifact_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetProblemResponse]:
    """Search problems from problems_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
    source_alias = "mv" if bypass_mv else "p"
    from_source = source if bypass_mv else f"{source} {source_alias}"

    rows = await conn.fetch(
        f"""
        SELECT {source_alias}.problem_id, {source_alias}.profile_id, c.session_id, {source_alias}.type, {source_alias}.message, {source_alias}.resolved, {source_alias}.created_at, {source_alias}.active, {source_alias}.mcp, {source_alias}.generated, {source_alias}.artifact_type
        FROM {from_source}
        JOIN problems_entry pe ON pe.id = {source_alias}.problem_id
        LEFT JOIN calls_entry c ON c.id = pe.call_id
        WHERE ($1::uuid[] IS NULL OR {source_alias}.profile_id = ANY($1))
          AND ($2::uuid[] IS NULL OR c.session_id = ANY($2))
          AND ($3::text IS NULL OR {source_alias}.type = $3)
          AND ($4::boolean IS NULL OR {source_alias}.resolved = $4)
          AND ($5::timestamptz IS NULL OR {source_alias}.created_at >= $5)
          AND ($6::timestamptz IS NULL OR {source_alias}.created_at <= $6)
          AND ($7::boolean IS NULL OR {source_alias}.mcp = $7)
          AND ($10::text IS NULL OR {source_alias}.artifact_type = $10)
        ORDER BY {source_alias}.created_at DESC
        LIMIT $8 OFFSET $9
        """,
        profile_ids,
        session_ids,
        type,
        resolved,
        date_from,
        date_to,
        mcp,
        limit + offset + 1000,
        0,
        artifact_type,
    )

    mv_dicts = [
        {
            "id": str(r["problem_id"]),
            "profile_id": str(r["profile_id"]) if r["profile_id"] else None,
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "type": r["type"],
            "message": r["message"],
            "resolved": r["resolved"],
            "created_at": r["created_at"],
            "active": r["active"],
            "mcp": r["mcp"],
            "generated": r["generated"],
            "artifact_type": r["artifact_type"],
        }
        for r in rows
    ]

    profile_ids_str = {str(p) for p in profile_ids} if profile_ids else None
    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def _parse_ts(ts):
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    def matches(row: dict) -> bool:
        if profile_ids_str is not None and str(row.get("profile_id")) not in profile_ids_str:
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        if type is not None and row.get("type") != type:
            return False
        if resolved is not None and row.get("resolved") != resolved:
            return False
        ts = _parse_ts(row.get("created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        if mcp is not None and row.get("mcp") != mcp:
            return False
        if artifact_type is not None and row.get("artifact_type") != artifact_type:
            return False
        return True

    merged = await hedged_search(
        redis,
        "problems",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetProblemResponse.model_validate(r) for r in merged]
