"""Refresh CREATE — insert into refresh_entry."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.refreshes.types import CreateRefreshResponse


async def create_refresh(
    conn: asyncpg.Connection,
    operation_key: UUID,
    artifact_type: str,
    target: str,
    session_id: UUID,
    mcp: bool = False,
) -> CreateRefreshResponse:
    """Create a refresh entry for an MV target."""
    refresh_id = await conn.fetchval(
        """
        INSERT INTO refresh_entry (operation_key, artifact_type, target, session_id, mcp, generated)
        VALUES ($1, $2::artifact_type, $3, $4, $5, true)
        RETURNING id
        """,
        operation_key,
        artifact_type,
        target,
        session_id,
        mcp,
    )

    if refresh_id is None:
        raise ValueError("Failed to create refresh entry")

    return CreateRefreshResponse(id=refresh_id)
