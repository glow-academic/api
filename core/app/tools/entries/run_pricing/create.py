"""run_pricing/create internal — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.run_pricing.types import CreateRunPricingEntryResponse
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_run_pricing_entry_internal(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    pricing_type: str,
    run_id: UUID,
    pricing_id: UUID | None = None,
    count: int = 0,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateRunPricingEntryResponse:
    """Create a run_pricing entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO run_pricing_entry (session_id, pricing_type, count, run_id, mcp, generated, active, created_at)
        VALUES ($1, $2, $3, $4, $5, true, $6, COALESCE($7, NOW()))
        RETURNING id, created_at
        """,
        session_id,
        pricing_type,
        count,
        run_id,
        mcp,
        not soft,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create run_pricing entry")
    entry_id = row["id"]
    actual_created_at = row["created_at"]

    if pricing_id is not None:
        await conn.execute(
            """
            INSERT INTO run_pricing_pricing_connection (run_pricing_id, pricing_id, active, generated, mcp)
            VALUES ($1, $2, true, true, $3)
            ON CONFLICT (run_pricing_id, pricing_id) DO NOTHING
            """,
            entry_id,
            pricing_id,
            mcp,
        )

    fresh_row = {
        "id": str(entry_id),
        "pricing_type": pricing_type,
        "count": count,
        "run_id": str(run_id),
        "session_id": str(session_id),
        "created_at": actual_created_at.isoformat(),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
    }
    await write_back_row(
        redis,
        "run_pricing",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )
    # Parent run's cached pricing breakdown is now stale.
    await invalidate_row(redis, "runs", run_id)

    return CreateRunPricingEntryResponse(id=entry_id)
