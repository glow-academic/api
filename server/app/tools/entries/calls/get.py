"""Calls GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.calls.types import GetCallResponse


async def get_call(
    conn: asyncpg.Connection,
    call_id: UUID,
) -> GetCallResponse | None:
    """Get a calls entry by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, run_id, session_id, external_call_id,
               created_at, active, mcp, generated
        FROM calls_entry
        WHERE id = $1
    """,
        call_id,
    )

    if row is None:
        return None

    return GetCallResponse(
        id=row["id"],
        run_id=row["run_id"],
        session_id=row["session_id"],
        external_call_id=row["external_call_id"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
