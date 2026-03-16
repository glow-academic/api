"""Resolves CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.resolves.types import CreateResolveResponse


async def create_resolve(
    conn: asyncpg.Connection,
    problem_id: UUID,
    resolved: bool,
    call_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateResolveResponse:
    """Create a resolves entry."""
    resolve_id = await conn.fetchval(
        """
        INSERT INTO resolves_entry (id, problem_id, resolved, call_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        problem_id,
        resolved,
        call_id,
        not soft,
        mcp,
        id,
    )

    if resolve_id is None:
        raise ValueError("Failed to create resolves entry")

    return CreateResolveResponse(id=resolve_id)
