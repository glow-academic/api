"""run_pricing/create internal — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.run_pricing.types import CreateRunPricingEntryResponse


async def create_run_pricing_entry_internal(
    conn: asyncpg.Connection,
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
    entry_id = await conn.fetchval(
        """
        INSERT INTO run_pricing_entry (session_id, pricing_type, count, run_id, mcp, generated, active, created_at)
        VALUES ($1, $2, $3, $4, $5, true, $6, COALESCE($7, NOW()))
        RETURNING id
        """,
        session_id,
        pricing_type,
        count,
        run_id,
        mcp,
        not soft,
        created_at,
    )

    if entry_id is None:
        raise ValueError("Failed to create run_pricing entry")

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

    return CreateRunPricingEntryResponse(id=entry_id)
