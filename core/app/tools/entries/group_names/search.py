"""Group names SEARCH — filtered query against group_names_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.group_names.types import GetGroupNameResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "group_names_mv"


async def search_group_names(
    conn: asyncpg.Connection,
    redis: Redis,
    group_ids: list[UUID] | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetGroupNameResponse]:
    """Search group names from group_names_mv."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, group_id, name, created_at, generated, mcp
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR group_id = ANY($1))
          AND ($2::text IS NULL OR name ILIKE '%' || $2 || '%')
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        group_ids,
        search,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "group_id": str(r["group_id"]),
            "name": r["name"],
            "created_at": r["created_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
        }
        for r in rows
    ]

    group_ids_str = {str(g) for g in group_ids} if group_ids else None
    search_lower = search.lower() if search else None

    def matches(row: dict) -> bool:
        if group_ids_str is not None and str(row.get("group_id")) not in group_ids_str:
            return False
        if search_lower is not None:
            name = row.get("name") or ""
            if search_lower not in name.lower():
                return False
        return True

    merged = await hedged_search(
        redis,
        "group_names",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="group_id",
        bypass_cache=bypass_cache,
    )
    return [GetGroupNameResponse.model_validate(r) for r in merged]
