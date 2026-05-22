"""Runs GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.runs.types import GetRunResponse
from app.utils.cache.hedged_row import read_back_row


async def get_run(
    conn: asyncpg.Connection,
    run_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetRunResponse | None:
    """Get a runs entry by ID (with cache hedge)."""
    if not bypass_cache:
        cached = await read_back_row(redis, "runs", run_id)
        if cached is not None:
            return GetRunResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, session_id, group_id, mcp, generated
        FROM runs_entry
        WHERE id = $1
    """,
        run_id,
    )

    if row is None:
        return None

    return GetRunResponse(
        id=row["id"],
        session_id=row["session_id"],
        group_id=row["group_id"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
