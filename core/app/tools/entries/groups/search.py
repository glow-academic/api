"""Groups search — filtered/paginated query against groups_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from datetime import datetime as _dt

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.groups.types import GetGroupResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "groups_mv"


async def search_groups(
    conn: asyncpg.Connection,
    redis: Redis,
    session_ids: list[UUID] | None = None,
    name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    artifact_type: str | None = None,
    has_runs: bool = False,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetGroupResponse]:
    """Search groups from groups_mv with declarative filters.

    has_runs=True drops groups that have no visible run. EXISTS check
    runs against runs_mv (not runs_entry) because that's the same
    universe the test picker's inner expansion sources from via
    search_runs — keeping the two aligned avoids "header shows up but
    expands to nothing" when runs_mv hasn't materialized base-table
    rows or the MV's join filters out the row. Short-circuits on the
    indexed group_id column.
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT group_id, session_id, created_at, name, active, mcp, generated, artifact_type
        FROM {source} g
        WHERE ($1::uuid[] IS NULL OR session_id = ANY($1))
          AND ($2::text IS NULL OR name ILIKE '%' || $2 || '%')
          AND ($3::timestamptz IS NULL OR created_at >= $3)
          AND ($4::timestamptz IS NULL OR created_at <= $4)
          AND ($5::boolean IS NULL OR mcp = $5)
          AND ($8::text IS NULL OR artifact_type = $8)
          AND (NOT $9::boolean OR EXISTS (
                SELECT 1 FROM runs_mv r
                WHERE r.group_id = g.group_id
                LIMIT 1
              ))
        ORDER BY created_at DESC
        LIMIT $6 OFFSET $7
        """,
        session_ids,
        name,
        date_from,
        date_to,
        mcp,
        limit + offset + 1000,
        0,
        artifact_type,
        has_runs,
    )

    mv_dicts = [
        {
            "id": str(r["group_id"]),
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "created_at": r["created_at"],
            "name": r["name"],
            "active": r["active"],
            "mcp": r["mcp"],
            "generated": r["generated"],
            "artifact_type": r["artifact_type"],
        }
        for r in rows
    ]

    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def _parse_ts(ts):
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    def matches(row: dict) -> bool:
        # has_runs requires DB existence check — cached rows are fresh
        # write-backs with no runs yet, so they can't satisfy this.
        if has_runs:
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        if name is not None:
            row_name = row.get("name") or ""
            if name.lower() not in row_name.lower():
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
        "groups",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetGroupResponse.model_validate(r) for r in merged]
