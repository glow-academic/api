"""Messages search — filtered/paginated query against messages_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.messages.types import SearchMessageResponse

MV_NAME = "messages_mv"


async def search_messages(
    conn: asyncpg.Connection,
    run_ids: list[UUID] | None = None,
    role: str | None = None,
    roles: list[str] | None = None,
    agent_ids: list[UUID] | None = None,
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> tuple[list[SearchMessageResponse], int]:
    """Search messages from messages_mv with declarative filters.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
    source_alias = "mv" if bypass_mv else "m"
    from_source = source if bypass_mv else f"{source} {source_alias}"

    order = "ASC" if sort_order.lower() == "asc" else "DESC"

    rows = await conn.fetch(
        f"""
        SELECT DISTINCT {source_alias}.message_id, {source_alias}.run_id, {source_alias}.role, {source_alias}.message_created_at,
               {source_alias}.text_upload_ids, {source_alias}.audio_upload_ids, {source_alias}.image_upload_ids,
               {source_alias}.video_upload_ids, {source_alias}.file_upload_ids, {source_alias}.call_upload_ids,
               COUNT(*) OVER() AS total_count
        FROM {from_source}
        LEFT JOIN messages_agents_connection mac ON mac.message_id = {source_alias}.message_id
        WHERE ($1::uuid[] IS NULL OR {source_alias}.run_id = ANY($1))
          AND ($2::text IS NULL OR {source_alias}.role = $2)
          AND ($3::uuid[] IS NULL OR mac.agents_id = ANY($3))
          AND ($4::text[] IS NULL OR {source_alias}.role = ANY($4))
        ORDER BY {source_alias}.message_created_at {order}
        LIMIT $5 OFFSET $6
        """,
        run_ids,
        role,
        agent_ids,
        roles,
        limit,
        offset,
    )

    total_count = rows[0]["total_count"] if rows else 0
    items = [
        SearchMessageResponse(
            **{k: v for k, v in dict(r).items() if k != "total_count"}
        )
        for r in rows
    ]
    return items, total_count
