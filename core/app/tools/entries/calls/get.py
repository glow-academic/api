"""Calls GET — batch get from calls_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.calls.types import GetCallResponse

MV_NAME = "calls_mv"


async def get_calls(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
) -> list[GetCallResponse]:
    """Get calls by IDs from calls_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT call_id, run_id, call_created_at,
               upload_id, file_path, mime_type, tool_id
        FROM {source}
        WHERE call_id = ANY($1)
        """,
        ids,
    )

    return [
        GetCallResponse(
            id=r["call_id"],
            run_id=r["run_id"],
            created_at=r["call_created_at"],
            upload_id=r["upload_id"],
            file_path=r["file_path"],
            mime_type=r["mime_type"],
            tool_id=r["tool_id"],
        )
        for r in rows
    ]
