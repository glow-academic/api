"""Calls search — filtered/paginated query against calls_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.calls.types import GetCallResponse
from app.utils.cache.hedged_row import hedged_search

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
    bypass_cache: bool = False,
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
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["call_id"]),
            "run_id": str(r["run_id"]) if r["run_id"] else None,
            "created_at": r["call_created_at"],
            "operation_key": str(r["operation_key"]) if r["operation_key"] else None,
            "upload_id": str(r["upload_id"]) if r["upload_id"] else None,
            "file_path": r["file_path"],
            "mime_type": r["mime_type"],
            "tool_id": str(r["tool_id"]) if r["tool_id"] else None,
        }
        for r in rows
    ]

    run_ids_str = {str(x) for x in run_ids} if run_ids else None
    tool_ids_str = {str(x) for x in tool_ids} if tool_ids else None
    op_keys_str = {str(x) for x in operation_keys} if operation_keys else None

    def matches(row: dict) -> bool:
        if run_ids_str is not None and str(row.get("run_id")) not in run_ids_str:
            return False
        if tool_ids_str is not None and str(row.get("tool_id")) not in tool_ids_str:
            return False
        if op_keys_str is not None and str(row.get("operation_key")) not in op_keys_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "calls",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetCallResponse.model_validate(r) for r in merged]
