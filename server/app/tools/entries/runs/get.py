"""Runs GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.runs.types import GetRunResponse


async def get_run(
    conn: asyncpg.Connection,
    run_id: UUID,
) -> GetRunResponse | None:
    """Get a runs entry by ID."""
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
