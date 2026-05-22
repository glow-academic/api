"""Problems CREATE — insert into problems_entry with profile link."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.problems.types import CreateProblemResponse
from app.utils.cache.hedged_row import write_back_row


async def create_problem(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    call_id: UUID,
    type: str,
    *,
    artifact_type: str,
    id: UUID | None = None,
    message: str = "No message provided",
    profile_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateProblemResponse:
    """Create a problem entry and optionally link to a profile."""
    row = await conn.fetchrow(
        """
        INSERT INTO problems_entry (id, call_id, type, message, active, mcp, generated, artifact_type, created_at)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true, $7, COALESCE($8, NOW()))
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active, mcp, artifact_type
        """,
        call_id,
        type,
        message,
        not soft,
        mcp,
        id,
        artifact_type,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create problem entry")
    problem_id = row["id"]
    actual_created_at = row["created_at"]

    if profile_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_problems_connection (profiles_id, problem_id)
            VALUES ($1, $2)
            """,
            profile_id,
            problem_id,
        )

    fresh_row = {
        "id": str(problem_id),
        "profile_id": str(profile_id) if profile_id else None,
        "session_id": str(session_id),
        "type": type,
        "message": message,
        "resolved": False,
        "created_at": actual_created_at.isoformat(),
        "active": row["active"],
        "mcp": row["mcp"],
        "generated": True,
        "artifact_type": row["artifact_type"],
    }
    await write_back_row(
        redis,
        "problems",
        problem_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateProblemResponse(id=problem_id)
