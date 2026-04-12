"""Group names SEARCH — filtered query against group_names_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.group_names.types import GetGroupNameResponse

MV_NAME = "group_names_mv"


async def search_group_names(
    conn: asyncpg.Connection,
    group_ids: list[UUID] | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
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
        limit,
        offset,
    )

    return [
        GetGroupNameResponse(
            id=r["id"],
            group_id=r["group_id"],
            name=r["name"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
        )
        for r in rows
    ]
