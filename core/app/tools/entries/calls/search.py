"""Calls search — filtered/paginated query against calls_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.calls.types import GetCallResponse

MV_NAME = "calls_mv"


async def search_calls(
    conn: asyncpg.Connection,
    redis: Redis,
    run_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    operation_keys: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetCallResponse]:
    """Search calls from calls_mv with declarative filters.

    ``operation_keys`` backs the idempotency replay gate: a hit returns the
    prior call's ``file_path`` (its persisted receipt) so the caller can replay
    the stored result instead of re-executing.
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT call_id, run_id, call_created_at, operation_key,
               upload_id, file_path, mime_type, tool_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR run_id = ANY($1))
          AND ($2::uuid[] IS NULL OR tool_id = ANY($2))
          AND ($3::uuid[] IS NULL OR operation_key = ANY($3))
        ORDER BY call_created_at DESC
        LIMIT $4 OFFSET $5
        """,
        run_ids,
        tool_ids,
        operation_keys,
        limit,
        offset,
    )

    return [
        GetCallResponse(
            id=r["call_id"],
            run_id=r["run_id"],
            created_at=r["call_created_at"],
            operation_key=r["operation_key"],
            upload_id=r["upload_id"],
            file_path=r["file_path"],
            mime_type=r["mime_type"],
            tool_id=r["tool_id"],
        )
        for r in rows
    ]
